"""tools/l2_audit —— L2 真机同桌审计（从 4 份 bot 日志还原每场各席得分并判定）。

输入：4 个 bot 的 --log 文件（logs/l2x1_<seat>.log，含各自 "策略: X" 标签与
每场 "本场积分 seat=N: [s0,s1,s2,s3]" 记录）。
输出：完整场次配对差统计（delta/sd/SE/CI/裁决）——口径同 L1 ab_analyze，
但 σ 由真机数据实测。

用法：
    python tools/l2_audit.py --room t_fb08f23caa81          # 自动找 logs/l2x1_*.log
    python tools/l2_audit.py --logs q=logs/a.log,e=logs/b.log ...
裁决：delta ≥ δ_min 且 CI 排除 0 → WIN（送合入）；CI 含 0 → DRAW/converged。
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re

SEAT_RE = re.compile(r"^.*本场结束: (.*?)（gid=(\S+)）$")
SCORE_RE = re.compile(r"^.*本场积分 seat=(\d+): (\[.*\])$")
STRAT_RE = re.compile(r"^.*策略: (\S+)")


def parse_log(path):
    """返回 (strat, {gid: (seat, scores)})。"""
    strat = None
    recs = {}
    pending_gid = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if strat is None:
                m = STRAT_RE.search(line)
                if m:
                    strat = m.group(1)
            m = SEAT_RE.search(line)
            if m:
                pending_gid = m.group(2)
                continue
            m = SCORE_RE.search(line)
            if m and pending_gid is not None:
                try:
                    scores = json.loads(m.group(2))
                except ValueError:
                    pending_gid = None
                    continue
                recs[pending_gid] = (int(m.group(1)), scores)
                pending_gid = None
    return strat, recs


def audit(log_specs, delta_min=2.0):
    """log_specs: [{name, path}]。返回统计 dict。"""
    per = {}
    for spec in log_specs:
        strat, recs = parse_log(spec["path"])
        spec["strat"] = strat
        per[spec["name"]] = recs
    gids = set()
    for recs in per.values():
        gids |= set(recs)
    ds = []
    skipped = {"incomplete": 0, "dup_seat": 0, "no_cand": 0}
    for gid in sorted(gids):
        seatmap = {}
        scores = None
        ok = True
        for name, recs in per.items():
            r = recs.get(gid)
            if not r:
                skipped["incomplete"] += 1
                ok = False
                break
            seat, sc = r
            if scores is None:
                scores = sc
            if seat in seatmap:
                skipped["dup_seat"] += 1
                ok = False
                break
            seatmap[seat] = name
        if not ok or scores is None:
            continue
        strat_of = {spec["name"]: spec.get("strat") for spec in log_specs}
        x1 = [scores[s] for s, n in seatmap.items()
              if strat_of.get(n) == "speedx1"]
        e = [scores[s] for s, n in seatmap.items()
             if strat_of.get(n) == "speedE"]
        if len(x1) != 2 or len(e) != 2:
            skipped["no_cand"] += 1
            continue
        d = (sum(x1) - sum(e)) / 2.0
        ds.append((gid, d))
    n = len(ds)
    if not n:
        return {"n": 0, "skipped": skipped}
    mean = sum(d for _, d in ds) / n
    var = sum((d - mean) ** 2 for _, d in ds) / n
    sd = math.sqrt(var)
    se = sd / math.sqrt(n)
    ci = (mean - 1.96 * se, mean + 1.96 * se)
    verdict = ("WIN" if mean >= delta_min and ci[0] > 0 else
               "LOSE" if ci[1] < 0 else
               "WEAK" if mean > 0 and ci[0] > 0 else "DRAW")
    return {"n": n, "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(se, 4), "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "delta_min": delta_min, "verdict": verdict,
            "skipped": skipped, "sample": ds[-20:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="*", default=[],
                    help="4 份日志（自动兜底 logs/l2x1_*.log）")
    ap.add_argument("--delta-min", type=float, default=2.0)
    args = ap.parse_args()
    paths = args.logs or sorted(glob.glob(os.path.join("logs", "l2x1_*.log")))
    if len(paths) != 4:
        print("需要 4 份日志，实际 %d（%s）；或 --logs 指定" % (len(paths), paths))
        return 3
    specs = [{"name": os.path.basename(p).replace(".log", "").replace(
        "l2x1_", ""), "path": p} for p in paths]
    a = audit(specs, args.delta_min)
    if not a["n"]:
        print("尚无完整场次记录（incomplete=%s dup=%s no_cand=%s）"
              % (a["skipped"].get("incomplete", 0),
                 a["skipped"].get("dup_seat", 0),
                 a["skipped"].get("no_cand", 0)))
        return 2
    print("真机同桌 L2: n=%d 场 delta=%+.3f/场 sd=%.2f SE=%.4f "
          "95%%CI=[%+.2f, %+.2f] verdict=%s" % (a["n"], a["delta"], a["sd"],
          a["se"], a["ci95"][0], a["ci95"][1], a["verdict"]))
    print(json.dumps({k: v for k, v in a.items() if k != "sample"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
