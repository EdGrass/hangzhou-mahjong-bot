"""tools/session_health —— 会话健康审计 + 同桌裁决（P1c/P2b 共用）。

对同一会话 N 份席位日志：
1) 健康统计：场次/409（按 phase+action 细分）/策略异常/[dperf] 慢决策/
   [xlog] 分歧数（执行验证）/vlog 计数 → 每席表 + 不对称指数；
2) 同桌配对裁决：每场 A/B 两侧均分差（A=候选或指定文件组，B=基准）→
   n/delta/sd/CI（与 tools/window_audit.py 同口径）；
3) 座位组合分解：A 占位 (a1,a2) 时的场均差——定位座对/位置偏倚。

用法：
  python tools/session_health.py --logs "logs/uA_*.log"
      # 默认角色：A=日志内策略标签非 speedE 的席位，B=speedE
  python tools/session_health.py --logs "logs/e4a_*.log" \
      --roles '{"qinglong":"A","baihu":"A","zhuque":"B","xuanwu":"B"}'
      # E×4 标定：全 E 时显式给文件组角色（文件名子串匹配）
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
INV_RE = re.compile(r"^.*动作 409（已失效）: (\S+) phase=(\S+) act=(\S+)")
INV_RE_OLD = re.compile(r"^.*动作 409（已失效）:")
XLOG_RE = re.compile(r"^.*\[xlog\]")
DPERF_RE = re.compile(r"^.*\[dperf\] decide (\d+(?:\.\d+)?)ms")
EXC_RE = re.compile(r"^.*策略异常")
VLOG_RE = re.compile(r"^.*\[vlog[VE]\]")


def parse_log(path):
    """返回 (strat, {gid:(seat,scores)}, health)。"""
    strat = None
    recs = {}
    health = {"finished": 0, "invalid": 0, "inv_phase": {}, "inv_act": {},
              "xlog": 0, "slow": 0, "slow_max_ms": 0.0, "exc": 0, "vlog": 0}
    pending = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STRAT_RE.search(line)
            if m and strat is None:
                strat = m.group(1)
            m = SEAT_RE.search(line)
            if m:
                pending = m.group(2)
                health["finished"] += 1
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
                continue
            m = INV_RE.search(line)
            if m:
                health["invalid"] += 1
                code, ph, act = m.group(1), m.group(2), m.group(3)
                health["inv_phase"][ph] = health["inv_phase"].get(ph, 0) + 1
                health["inv_act"][act] = health["inv_act"].get(act, 0) + 1
                continue
            if INV_RE_OLD.search(line):     # 旧格式日志（无 phase 细目）
                health["invalid"] += 1
                health["inv_phase"]["old"] = health["inv_phase"].get("old", 0) + 1
                continue
            if XLOG_RE.search(line):
                health["xlog"] += 1
                continue
            m = DPERF_RE.search(line)
            if m:
                ms = float(m.group(1))
                health["slow"] += 1
                health["slow_max_ms"] = max(health["slow_max_ms"], ms)
                continue
            if EXC_RE.search(line):
                health["exc"] += 1
                continue
            if VLOG_RE.search(line):
                health["vlog"] += 1
    return strat, recs, health


def _stats(ds):
    if not ds:
        return {"n": 0, "delta": None, "sd": None, "se": None, "ci95": None}
    mean = sum(ds) / len(ds)
    sd = math.sqrt(sum((d - mean) ** 2 for d in ds) / len(ds))
    se = sd / math.sqrt(len(ds))
    return {"n": len(ds), "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(se, 4),
            "ci95": [round(mean - 1.96 * se, 3), round(mean + 1.96 * se, 3)]}


def audit(specs, roles):
    """specs: [{"name","path","strat"}...]；roles: 显式 name→A/B 或 None 自动。"""
    per, health = {}, {}
    for s in specs:
        strat, recs, h = parse_log(s["path"])
        per[s["name"]] = (strat, recs)
        health[s["name"]] = h
    ds, combos = [], {}
    for gid in sorted(set().union(*[set(r[1]) for r in per.values()]) if per
                      else set()):
        seatmap, scores = {}, None
        ok = True
        for name, (_, recs) in per.items():
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
        side = {}
        for seat, name in seatmap.items():
            if roles is not None:
                side[seat] = roles.get(name)
            else:
                st = per[name][0]
                side[seat] = "A" if st and st != "speedE" else "B"
        seats_a = [s for s, v in side.items() if v == "A"]
        seats_b = [s for s, v in side.items() if v == "B"]
        if not seats_a or not seats_b:
            continue
        da = sum(scores[s] for s in seats_a) / len(seats_a)
        db = sum(scores[s] for s in seats_b) / len(seats_b)
        ds.append(da - db)
        key = tuple(sorted(seats_a))
        combos.setdefault(key, []).append(da - db)
    out = {"files": {}, "delta": _stats(ds), "combo_delta": {}}
    for name, h in health.items():
        strat, recs = per[name]
        out["files"][name] = {
            "strat": strat, "games": h["finished"], "records": len(recs),
            "invalid": h["invalid"], "invalid_per_game":
                round(h["invalid"] / h["finished"], 2) if h["finished"] else None,
            "inv_phase": h["inv_phase"], "inv_act": h["inv_act"],
            "xlog": h["xlog"], "slow_decides": h["slow"],
            "slow_max_ms": h["slow_max_ms"], "exc": h["exc"],
            "vlog_lines": h["vlog"]}
    for key in sorted(combos):
        out["combo_delta"]["%d%d" % key] = _stats(combos[key])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", required=True)
    ap.add_argument("--roles", default="", help="JSON: 文件名子串→A/B（E×4 标定用）")
    ap.add_argument("--json", action="store_true", help="纯 JSON 输出")
    args = ap.parse_args()
    paths = []
    for p in args.logs:
        paths += glob.glob(p) if glob.has_magic(p) else [p]
    paths = sorted(set(paths))
    if len(paths) < 2:
        print("需要 ≥2 份日志")
        return 3
    specs = [{"name": os.path.basename(p), "path": p} for p in paths]
    roles = None
    if args.roles:
        m = json.loads(args.roles)
        roles = {}
        for sub, side in m.items():
            for s in specs:
                if sub in s["name"]:
                    roles[s["name"]] = side
        missing = [s["name"] for s in specs if s["name"] not in roles]
        if missing:
            print("roles 未覆盖: %s" % missing)
            return 3
    out = audit(specs, roles)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
