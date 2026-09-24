# -*- coding: utf-8 -*-
"""our_action_audit —— 从**本地决策流**统计"我方自己的"动作频率（逐席口径，不依赖门户发布）。

为什么有用（2026-09-16）：机制核对（如 c150 的"杠/轮"）过去要等门户复盘发布；
但本地 `var/replays/auto_*/*.dec.jsonl` 里每条都是**我们自己的一个决策**：
  - `s` = **该局我们坐的座位号**（每局轮换 ⇒ 0-3 都会出现，这**不是**"一桌四家"的意思）；
  - `p` = 决策类型（`draw` / `response_peng` / `response_chi` …）；
  - `a.action` = 我们实际发出的动作（`discard/chi/peng/gang/hu/pass`）。

输出（按策略/按房）：摸牌数、各动作计数、以及 **动作/摸牌** 比率。

用法：
    python -X utf8 tools/our_action_audit.py                      # 自动按 var/.ab_mode 分臂
    python -X utf8 tools/our_action_audit.py --arms speedtugc,speedc150
    python -X utf8 tools/our_action_audit.py --since "2026-09-16 13:43:02"
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")


def campaign():
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return [], None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    return [str(x) for x in (arms or []) if x], cfg.get("started")


def ranking_index():
    """返回 (room->strategy, [(ts, strategy, room)])。"""
    by_room, rows = {}, []
    p = os.path.join(ROOT, "var", "auto_ranking.jsonl")
    if not os.path.exists(p):
        return by_room, rows
    try:
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            room = d.get("room") or ""
            st = d.get("strategy") or "?"
            if room:
                by_room[room] = st
            rows.append((d.get("ts") or "", st, room))
    except Exception:
        pass
    return by_room, rows


def strategy_of(dirname, room, by_room, rows):
    """先按 room_id 精确匹配；匹配不到就按目录时间戳找"完成时间最接近"的那一房（备用）。

    已知局限（2026-09-16）：备用匹配会把正在跑/未归档的房错配到别的臂
    （实测 auto_20260916_142547 被标成 speedtugc，实际是 speedc150）。
    需要严格逐臂口径时，请以 var/_ab_log.jsonl 的排批记录为准（那里有 arm 字段），
    或等该房进入 auto_ranking.jsonl 后重跑本工具。不要用备用匹配的结果下结论。
    """
    if room and room in by_room:
        return by_room[room]
    ts = ""
    if dirname.startswith("auto_") and len(dirname) >= 19:
        ts = "%s-%s-%s %s:%s:%s" % (dirname[5:9], dirname[9:11], dirname[11:13],
                                     dirname[14:16], dirname[16:18], dirname[18:20])
    if ts:
        best, bd = None, None
        for rts, st, _r in rows:
            if not rts:
                continue
            d = abs(_tsdiff(rts, ts))
            if bd is None or d < bd:
                bd, best = d, st
        if best is not None and bd is not None and bd <= 3600:
            return best
    return None


def _tsdiff(a, b):
    """两个 'YYYY-MM-DD HH:MM:SS' 的秒差（解析失败返回一个很大的数）。"""
    import datetime as _dt
    try:
        fa = _dt.datetime.strptime(a[:19], "%Y-%m-%d %H:%M:%S")
        fb = _dt.datetime.strptime(b[:19], "%Y-%m-%d %H:%M:%S")
        return (fa - fb).total_seconds()
    except Exception:
        return 1e9


def scan_room_dir(dd):
    """纯函数：返回 Counter（我方动作计数）。"""
    c = collections.Counter()
    for f in glob.glob(os.path.join(dd, "*.dec.jsonl")):
        try:
            with io.open(f, encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    if not isinstance(r, dict):
                        continue
                    p = r.get("p")
                    if p == "draw":
                        c["draws"] += 1                 # 我方摸牌数（近似"轮"的口径）
                    a = (r.get("a") or {}).get("action")
                    if a:
                        c["act_" + str(a)] += 1
                    c["records"] += 1
        except Exception:
            pass
    return c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="")
    ap.add_argument("--since", default="")
    ap.add_argument("--dirs", default="auto_*")
    a = ap.parse_args(argv)
    arms, started = campaign()
    if a.arms.strip():
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    since = a.since or started or ""
    by_room, rows = ranking_index()
    per_arm = collections.defaultdict(collections.Counter)
    rooms = []
    for dd in sorted(glob.glob(os.path.join(ROOT, "var", "replays", a.dirs))):
        name = os.path.basename(dd)
        if not name.startswith("auto_"):
            continue
        if since and len(name) >= 19:
            dts = "%s-%s-%s %s:%s:%s" % (name[5:9], name[9:11], name[11:13],
                                         name[14:16], name[16:18], name[18:20])
            if dts < since[:19]:
                continue
        room = None
        fs = glob.glob(os.path.join(dd, "*.json"))
        if fs:
            room = os.path.basename(fs[0]).split("_r")[0]
        st = strategy_of(name, room, by_room, rows)
        c = scan_room_dir(dd)
        if not c["records"]:
            continue
        key = st or "?"
        per_arm[key].update(c)
        rooms.append((name, key, c["draws"], c["act_gang"], c["act_peng"], c["act_chi"], c["act_hu"]))
    if not rooms:
        print("（没有可统计的房）")
        return
    print("=" * 86)
    print("我方动作审计（逐席口径，来自本地决策流；轮≈摸牌数）")
    print("-" * 86)
    print("%-16s %7s %7s %8s %8s %8s %8s" % ("策略", "房数", "摸牌", "杠", "碰", "吃", "胡"))
    order = arms or sorted(per_arm)
    for st in order:
        c = per_arm.get(st)
        if not c or not c["draws"]:
            continue
        nr = sum(1 for r in rooms if r[1] == st)
        print("%-16s %7d %7d %8d %8d %8d %8d" % (st, nr, c["draws"], c["act_gang"], c["act_peng"], c["act_chi"], c["act_hu"]))
        print("   /轮: 杠 %.4f  碰 %.4f  吃 %.4f  胡 %.4f"
              % (c["act_gang"] / c["draws"], c["act_peng"] / c["draws"],
                 c["act_chi"] / c["draws"], c["act_hu"] / c["draws"]))
    print("-" * 86)
    print("逐房（只列前 30 个有数据的房）：")
    print("%-24s %-14s %6s %5s %5s %5s %5s" % ("dir", "strategy", "draws", "gang", "peng", "chi", "hu"))
    for row in rooms[:30]:
        print("%-24s %-14s %6d %5d %5d %5d %5d" % row)
    print("=" * 86)


if __name__ == "__main__":
    main()
