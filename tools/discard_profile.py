# -*- coding: utf-8 -*-
"""server 复盘弃牌牌型画像：冠军 vs 我们弃牌类别分布（找路径差异）。

对每场每局每座每次弃牌分类（基于弃前手牌与弃牌 t）：
  H    孤张字牌弃（手牌该字仅 1）
  HP   字牌对拆（手牌该字 2）
  WH   弃白板
  DP   数牌对拆（手牌该数 2）
  DQ   数牌刻/杠拆（>=3）
  DT   拆搭（孤张但有同花邻接在手：|n-2|~|n+2| 任一在手，且不成完整顺）
  ES   孤边张（1/9 无边邻）
  MS   孤中张（2-8 无边邻）
聚合按 user；对照 ME_UID（貔貅=我方）与其他（对手池）。
用法：python tools/discard_profile.py [--prefix a_xxx]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mahjong.tiles import is_suit_tile  # noqa: E402  (实为 34 维索引工具)

ME_UID = "u_7a3fba48d70b"
SUITS = "wbt"


def classify(hand, t):
    """返回弃牌类别（hand 为弃前手牌）。"""
    if t == "白":
        return "WH"
    if t in "东南西北中发":
        return "HP" if hand.count(t) == 2 else "H"
    cnt = hand.count(t)
    if cnt >= 3:
        return "DQ"
    if cnt == 2:
        return "DP"
    n, suit = int(t[0]), t[1]
    near = False
    for d in (-2, -1, 1, 2):
        nn = n + d
        if 1 <= nn <= 9 and "%d%s" % (nn, suit) in hand:
            near = True
            break
    if not near:
        return "ES" if n in (1, 9) else "MS"
    # 邻接在手：是搭子成员（含完整顺拆张）
    return "DT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()
    files = sorted(glob.glob("var/replays/server/*.json"))
    if args.prefix:
        files = [f for f in files
                 if os.path.basename(f).startswith(args.prefix)]
    agg = {}     # uid -> {cat: n}
    names = {}
    from tenpai_race import _rounds  # noqa: E402
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        seats = d.get("seats") or []
        uid_of = {i: s.get("user_id") for i, s in enumerate(seats)}
        for s in seats:
            names.setdefault(s.get("user_id"), s.get("name"))
        for rn, dealer, sh, evs in _rounds(d):
            if not sh or len(sh) != 4:
                continue
            hands = [list(h) for h in sh]
            melds = [[] for _ in range(4)]
            for e in evs:
                t, seat = e.get("type"), e.get("seat")
                if seat is None:
                    continue
                if t == "tile_drawn" and e.get("tile"):
                    hands[seat].append(e["tile"])
                elif t == "tile_discarded" and e.get("tile"):
                    tl = e["tile"]
                    if tl in hands[seat]:
                        a = agg.setdefault(uid_of.get(seat, "?"), {})
                        a["TOTAL"] = a.get("TOTAL", 0) + 1
                        cat = classify(hands[seat], tl)
                        a[cat] = a.get(cat, 0) + 1
                        hands[seat].remove(tl)
                elif t == "chi":
                    got = (e.get("data") or {}).get("tiles") or []
                    for x in got:
                        if x != e.get("tile") and x in hands[seat]:
                            hands[seat].remove(x)
                elif t == "peng":
                    for _ in range(2):
                        if e.get("tile") in hands[seat]:
                            hands[seat].remove(e.get("tile"))
                elif t == "gang":
                    kind = (e.get("data") or {}).get("kind")
                    if kind == "bu":
                        if e.get("tile") in hands[seat]:
                            hands[seat].remove(e.get("tile"))
                    elif kind == "an":
                        for _ in range(4):
                            if e.get("tile") in hands[seat]:
                                hands[seat].remove(e.get("tile"))
                    else:
                        for _ in range(3):
                            if e.get("tile") in hands[seat]:
                                hands[seat].remove(e.get("tile"))
    cats = ["H", "HP", "WH", "DP", "DQ", "DT", "ES", "MS"]
    me = agg.get(ME_UID)
    print("== 我方（%s）==" % names.get(ME_UID))
    if me:
        tot = me.get("TOTAL", 0)
        for c in cats:
            print("  %-4s %6d  %5.1f%%" % (c, me.get(c, 0),
                                            100.0 * me.get(c, 0) / tot))
        print("  TOTAL", tot)
    print("== 对手（按弃牌量排序，取前 12）==")
    opp = [(uid, a) for uid, a in agg.items() if uid != ME_UID]
    opp.sort(key=lambda kv: -kv[1].get("TOTAL", 0))
    print("  %-20s %7s" % ("name", "TOTAL") +
          "".join("%8s" % c for c in cats))
    for uid, a in opp[:12]:
        tot = a.get("TOTAL", 0)
        row = "  %-20s %7d" % ((names.get(uid) or uid)[:20], tot)
        for c in cats:
            row += "%8.1f" % (100.0 * a.get(c, 0) / tot)
        print(row)
    # 合并对手池
    a_all = {}
    for uid, a in agg.items():
        if uid == ME_UID:
            continue
        for k, v in a.items():
            a_all[k] = a_all.get(k, 0) + v
    tot = a_all.get("TOTAL", 0)
    print("== 对手池合计 ==")
    for c in cats:
        print("  %-4s %6d  %5.1f%%" % (c, a_all.get(c, 0),
                                        100.0 * a_all.get(c, 0) / tot))


if __name__ == "__main__":
    main()
