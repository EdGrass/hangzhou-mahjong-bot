# -*- coding: utf-8 -*-
"""dealopen_audit —— 庄家首弃（每局第一个动作）的执行缺陷审计。

背景（2026-09-18）：门户事件流显示，我方"庄家开局首弃"有近一半是**服务端代打**
（`tile_discarded` 后紧跟同席 `timeout{kind:"discard"}`）。bot 自己的事件录制
（var/replays/auto_*/*.jsonl）在该处**整段缺失**（例：764 round_ended → 767，
765=我方首弃 / 766=超时标记从未收到）⇒ 我们根本没看到那个窗口。

口径：
  · 只取有 start_hands 的 block，庄家手牌 14 张，且 block 首个事件就是该庄家的弃牌；
  · 代打判定 = 其后 1~2 条内出现同席 `timeout{kind:"discard"}`；
  · 定价 = 该弃牌相对"同向听层最大真进张"的损失（bot 同一把尺子 real_ukeire）。

用法：python -X utf8 tools/dealopen_audit.py
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as SH     # noqa: E402
from bot.ukeire import real_ukeire                  # noqa: E402
ME = "u_7a3fba48d70b"


def board_top(n=32):
    try:
        ctx = ssl._create_unverified_context()
        ck = open(os.path.join(ROOT, "var", ".portal_cookie"),
                  encoding="utf-8-sig").read().strip()
        req = urllib.request.Request(
            "https://10.240.169.190:18080/portal/api/leaderboard?period=all",
            headers={"Cookie": ck})
        d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                       .read().decode("utf-8"))
        return {p["user_id"] for p in (d.get("top") or [])[:n]}
    except Exception:
        return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="只统计该时刻之后开始的房（同 ab_readout 口径）")
    ap.add_argument("--no-cost", action="store_true", help="跳过进张定价（快）")
    args = ap.parse_args()
    top = board_top(32)
    C = collections.defaultdict(collections.Counter)
    P = collections.defaultdict(collections.Counter)    # 我方按策略
    smap = {}
    for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("room"):
            smap[r["room"]] = (r.get("strategy") or "?", r.get("ts") or "")
    seen = set()
    for dd in ("server", "recent"):
        for f in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                p = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            gid = p.get("game_id") or ""
            if not gid or gid in seen:
                continue
            info = smap.get(gid.split("_r")[0])
            if args.since and (not info or info[1] < args.since):
                continue
            seats = p.get("seats") or []
            if len(seats) != 4:
                continue
            uids = [s.get("user_id") or "" for s in seats]
            seen.add(gid)
            for b in p.get("blocks") or []:
                sh = b.get("start_hands")
                if not sh or any(h is None for h in sh):
                    continue
                evs = b.get("events") or []
                if not evs:
                    continue
                dl = b.get("dealer")
                if dl is None or len(sh[dl]) != 14:
                    continue
                e0 = evs[0]
                if e0.get("type") != "tile_discarded" or e0.get("seat") != dl:
                    continue
                u = uids[dl]
                g = "me" if u == ME else ("top" if u in top else "oth")
                tmo = any(e2.get("type") == "timeout" and e2.get("seat") == dl and
                          (e2.get("data") or {}).get("kind") == "discard"
                          for e2 in evs[1:3])
                C[g]["n"] += 1
                C[g]["tmo"] += 1 if tmo else 0
                if g != "me":
                    continue
                st = info[0] if info else "?"
                P[st]["n"] += 1
                P[st]["tmo"] += 1 if tmo else 0
                tile, hand = e0.get("tile"), list(sh[dl])
                if tile not in hand or args.no_cost:
                    continue
                vis = collections.Counter(hand)
                try:
                    best, ub, ua, sa = 99, 0, 0, None
                    for t in set(hand):
                        h2 = list(hand)
                        h2.remove(t)
                        s = SH(h2, qidui=True, exposed_melds=0, gangs=0)
                        uu, _k = real_ukeire(h2, exposed=0, gangs=0, visible=vis)
                        uu = 0 if uu is None else uu
                        if s < best:
                            best, ub = s, uu
                        elif s == best and uu > ub:
                            ub = uu
                        if t == tile:
                            ua, sa = uu, s
                    if sa is not None:
                        tag = "TMO" if tmo else "OK"
                        C[tag + "_cost"]["n"] += 1
                        C[tag + "_cost"]["loss"] += max(0, ub - ua) if sa == best else 0
                        C[tag + "_cost"]["pos"] += 1 if (sa == best and ua < ub) else 0
                except Exception:
                    pass
    print("=" * 84)
    print("庄家首弃（每局第一个动作）执行审计 —— 门户四家事件流，去重 %d 场" % len(seen))
    print("=" * 84)
    print("%-8s %8s %8s %9s" % ("组", "庄家首弃", "代打", "代打率"))
    for g, lab in (("me", "我方"), ("top", "top32"), ("oth", "其他")):
        c = C[g]
        print("%-8s %8d %8d %8.2f%%" % (lab, c["n"], c["tmo"],
                                        100.0 * c["tmo"] / max(1, c["n"])))
    print()
    print("代打掉多少进张（我方）：")
    for tag, lab in (("OK", "我方自己的选择"), ("TMO", "服务端代打")):
        c = C[tag + "_cost"]
        n = c["n"] or 1
        print("  %-14s n=%6d 均进张损失=%.3f 有损失占比=%.1f%%"
              % (lab, c["n"], c["loss"] / n, 100.0 * c["pos"] / n))
    print()
    print("我方按策略：")
    for st, c in sorted(P.items(), key=lambda kv: -kv[1]["n"])[:10]:
        if c["n"] < 40:
            continue
        print("  %-16s n=%6d 代打率=%5.2f%%" % (st, c["n"], 100.0 * c["tmo"] / c["n"]))


if __name__ == "__main__":
    main()
