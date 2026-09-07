"""tools/window_audit —— 正式赛窗口 N 席位审计（SpeedE vs 候选同赛段）。

按 gid 跨日志配对还原每场各席得分 → 配对差统计 + 裁决。
模式：
  same-table：同一 gid 内同时含两种策略席位才计入（同桌对照，最干净）；
  block：同一 gid 前缀（t_xxx_rNNN）内聚合两策略所有席位的场均差（分桌对照）。
用法：
  python tools/window_audit.py --logs "logs/w1_*.log" [--mode same-table|block]
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
GID_BLOCK = re.compile(r"^(t_\w+?)_r(\d+)")


def parse_log(path):
    """返回 (strat, {gid: (seat, scores)})。"""
    strat = None
    recs = {}
    pending = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STRAT_RE.search(line)
            if m and strat is None:
                strat = m.group(1)
            m = SEAT_RE.search(line)
            if m:
                pending = m.group(2)
                continue
            m = SCORE_RE.search(line)
            if m and pending is not None:
                try:
                    scores = json.loads(m.group(2))
                except ValueError:
                    pending = None
                    continue
                recs[pending] = (int(m.group(1)), scores)
                pending = None
    return strat, recs


def _finish(ds, mode, delta_min):
    n = len(ds)
    if not n:
        return {"n": 0, "delta": None, "sd": None, "se": None,
                "ci95": None, "delta_min": delta_min, "verdict": "NO_DATA",
                "mode": mode}
    mean = sum(ds) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in ds) / n)
    se = sd / math.sqrt(n)
    ci = (mean - 1.96 * se, mean + 1.96 * se)
    verdict = ("WIN" if mean >= delta_min and ci[0] > 0 else
               "LOSE" if ci[1] < 0 else
               "WEAK" if mean > 0 and ci[0] > 0 else "DRAW")
    return {"n": n, "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(se, 4), "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "delta_min": delta_min, "verdict": verdict, "mode": mode}


def _collect_blocks(per, strat_of):
    """逐日志独立收集（容忍缺场）：block = gid 前缀 t_xxx_rNNN，无匹配用 gid 自身。

    该路径不受 same-table 完整性门槛约束：任一日志缺某 gid 只让该块少贡献
    一席，不整体丢弃。返回每块候选均值 - 基准均值差值的列表。
    """
    blocks = {}
    for name, recs in per.items():
        st = strat_of.get(name)
        if not st:
            continue
        for gid, (seat, scores) in recs.items():
            m = GID_BLOCK.match(gid)
            key = m.group(0) if m else gid
            b = blocks.setdefault(key, {"cand": [], "base": []})
            if st == "speedE":
                b["base"].append(scores[seat])
            else:
                b["cand"].append(scores[seat])
    ds = []
    for b in blocks.values():
        if b["cand"] and b["base"]:
            ds.append(sum(b["cand"]) / len(b["cand"])
                      - sum(b["base"]) / len(b["base"]))
    return ds


def audit_logs(specs, mode="same-table", delta_min=2.0):
    """specs: [{"name": .., "path": ..}]。候选 = 日志内策略标签非 speedE 者。"""
    per = {}
    strat_of = {}
    for s in specs:
        strat, recs = parse_log(s["path"])
        per[s["name"]] = recs
        strat_of[s["name"]] = strat
    gids = set().union(*[set(r) for r in per.values()]) if per else set()
    same_ds = []
    # same-table：同桌对照，要求该场对所有日志同刻在场且 seat 不冲突。
    for gid in sorted(gids):
        seatmap = {}
        scores = None
        ok = True
        for name, recs in per.items():
            r = recs.get(gid)
            if not r:
                ok = False
                break
            seat, sc = r
            if scores is None:
                scores = sc
            if seat in seatmap:
                ok = False
                break
            seatmap[seat] = name
        if not ok or scores is None:
            continue
        cand = [scores[s] for s, n in seatmap.items()
                if strat_of.get(n) and strat_of[n] != "speedE"]
        base = [scores[s] for s, n in seatmap.items()
                if strat_of.get(n) == "speedE"]
        if cand and base:
            same_ds.append((sum(cand) / len(cand)) - (sum(base) / len(base)))
    if mode == "same-table":
        return _finish(same_ds, mode, delta_min)
    return _finish(_collect_blocks(per, strat_of), "block", delta_min)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", required=True)
    ap.add_argument("--mode", choices=("same-table", "block"),
                    default="same-table")
    ap.add_argument("--delta-min", type=float, default=2.0)
    args = ap.parse_args()
    paths = []
    for p in args.logs:
        paths += glob.glob(p) if glob.has_magic(p) else [p]
    paths = sorted(set(paths))
    if len(paths) < 2:
        print("需要 ≥2 份日志")
        return 3
    specs = [{"name": os.path.basename(p), "path": p} for p in paths]
    res = audit_logs(specs, mode=args.mode, delta_min=args.delta_min)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return {"WIN": 0, "DRAW": 2, "LOSE": 1, "WEAK": 2,
            "NO_DATA": 3}.get(res["verdict"], 3)


if __name__ == "__main__":
    raise SystemExit(main())
