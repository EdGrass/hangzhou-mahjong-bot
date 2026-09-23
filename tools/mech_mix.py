# -*- coding: utf-8 -*-
"""mech_mix —— A/B 两臂的**机制构成**核对：杠（明/暗/补）/财飘/爆头/七对/杠开/4白 的真实发生率。

为什么需要它：`ab_mechanism.py` 只看**弃牌层**（真进张遗憾、拆对率、听牌率），
而 c150 / c147 这些"束"的干预点在**动作类**——明杠、自杠（暗杠/补杠）、财飘（弃白）。
若干预根本没发生（例如我们的明杠率没升上去），那么"分数没动"就不是策略无效，而是**干预没生效** ⇒
应该立刻停臂，而不是等 150 房。本工具就是那张"干预是否真的发生"的表（**不是判据**）。

口径：
  - 数据 = 门户 `var/replays/{server,recent}/*.json`（**四家全信息**，`round_ended.data.detail` 是服务器权威）；
  - 房间 → 策略 的归属来自 `var/auto_ranking.jsonl`；
  - 只统计**我方那一席**。

用法：
    python -X utf8 tools/mech_mix.py                     # 自动取当前战役的两臂
    python -X utf8 tools/mech_mix.py --arms a,b --since "2026-09-18 00:00:00"
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ME = "u_7a3fba48d70b"
AB = os.path.join(ROOT, "var", ".ab_mode")


def _campaign_arms():
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return []
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    return [str(x) for x in (arms or []) if x]


def _strategy_map():
    """room_id -> (strategy, ts)"""
    out = {}
    p = os.path.join(ROOT, "var", "auto_ranking.jsonl")
    if not os.path.exists(p):
        return out
    for ln in io.open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("room"):
            out[d["room"]] = (d.get("strategy") or "?", d.get("ts") or "")
    return out


def scan_room(d):
    """返回 (我方座位号, Counter) —— 纯函数，便于单测。"""
    ids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
    if len(ids) != 4 or ME not in ids:
        return None, None
    me = ids.index(ME)
    c = collections.Counter()
    for b in d.get("blocks") or []:
        for e in b.get("events") or []:
            t, s = e.get("type"), e.get("seat")
            if t == "round_ended":
                data = e.get("data") or {}
                c["rounds"] += 1
                if isinstance(s, int) and s == me and not data.get("draw"):
                    c["wins"] += 1
                    det = [str(x) for x in (data.get("detail") or [])]
                    c["fan_sum"] += int(data.get("fan") or 0)
                    if "爆头" in det:
                        c["baotou"] += 1
                    if any("财飘" in x for x in det):
                        c["piao"] += 1
                    if "杠开" in det or any("杠飘链" in x for x in det):
                        c["ganghu"] += 1
                    if any(x.startswith("七对") or x.startswith("豪华七对") for x in det):
                        c["qidui"] += 1
                    if "4个白板" in det:
                        c["white4"] += 1
            elif t == "gang" and isinstance(s, int) and s == me:
                kind = (e.get("data") or {}).get("kind")
                c["gang_%s" % (kind or "?")] += 1
                c["gang_all"] += 1
    return me, c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="", help="逗号分隔；缺省取当前战役两臂")
    ap.add_argument("--since", default="", help="只统计该时间戳之后的房（与 ab_readout 的 started 同口径）")
    ap.add_argument("--dirs", default="server,recent")
    a = ap.parse_args(argv)
    arms = [x.strip() for x in a.arms.split(",") if x.strip()] or _campaign_arms()
    if not arms:
        raise SystemExit("无臂可看（--arms 或先启动 A/B）")
    smap = _strategy_map()
    tot = {k: collections.Counter() for k in arms}
    seen = set()
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        for p in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            gid = d.get("game_id") or ""
            room = gid.split("_r")[0]
            info = smap.get(room)
            if not info:
                continue
            st, ts = info
            if st not in arms or room in seen:
                continue
            if a.since and ts < a.since:
                continue
            me, c = scan_room(d)
            if me is None:
                continue
            seen.add(room)
            tot[st].update(c)
    print("机制构成核对（since=%s，⚠ 仅作「干预是否生效」，不是判据）" % (a.since or "-"))
    hdr = ("arm", "rooms", "我方局", "胜率", "杠/轮", "明杠", "暗杠", "补杠",
           "爆头%", "财飘%", "杠开%", "七对%", "4白%", "均番")
    print("%-14s %6s %6s %6s %7s %5s %5s %5s %6s %6s %6s %6s %6s %6s" % hdr)
    for st in arms:
        c = tot[st]
        r = max(1, c["rounds"])
        w = max(1, c["wins"])
        vals = [st, c["rounds"] // 80 if c["rounds"] else 0, c["rounds"],
                "%.1f%%" % (100.0 * c["wins"] / r) if c["rounds"] else "-",
                "%.4f" % (c["gang_all"] / r), c["gang_ming"], c["gang_an"], c["gang_bu"],
                "%.1f%%" % (100.0 * c["baotou"] / w), "%.1f%%" % (100.0 * c["piao"] / w),
                "%.1f%%" % (100.0 * c["ganghu"] / w), "%.1f%%" % (100.0 * c["qidui"] / w),
                "%.1f%%" % (100.0 * c["white4"] / w),
                "%.2f" % (c["fan_sum"] / w)]
        print("%-14s %6d %6d %6s %7s %5d %5d %5d %6s %6s %6s %6s %6s %6s" % tuple(vals))
    print()
    print("读法：c150/c147 这类束要让 **杠/轮、财飘%、爆头%** 明显高于基线臂；若这些没动 ⇒ 干预没生效，应停臂而非等分数。")


if __name__ == "__main__":
    raise SystemExit(main())
