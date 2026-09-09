# -*- coding: utf-8 -*-
"""server 复盘四家状态机：每局每座听牌巡号/等待 → '听牌竞赛'分析。

输入：var/replays/server/<gid>.json（blocks 全信息：start_hands + 全事件含
各家摸牌 tile）。每局跟踪四家手牌/副露，记录每家【第几次摸牌时向听=0】与
【最终胡者】。输出按策略侧聚合：平均听牌巡号、听牌→胡等待、胡率等。
用法：python tools/tenpai_race.py [--limit 场数]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mahjong.shanten_exact import shanten as S  # noqa: E402

ME_UID = "u_7a3fba48d70b"


def _rounds(data):
    """按 round_no 归并 blocks → [(round_no, dealer, start_hands, events)]。"""
    groups = {}
    for b in data.get("blocks", []):
        rn = b.get("round_no")
        g = groups.setdefault(rn, {"blocks": []})
        g["blocks"].append(b)
    out = []
    for rn in sorted(groups):
        g = groups[rn]
        bb = g["blocks"]
        evs = []
        for b in bb:
            evs.extend(b.get("events", []))
        evs.sort(key=lambda e: e.get("seq", 0))
        out.append((rn, bb[0].get("dealer"), bb[0].get("start_hands"), evs))
    return out


def run_round(start_hands, events, dealer):
    """返回 (hu_seat, tenpai_at) —— tenpai_at[seat] = 首次听牌的摸牌序号或 None。"""
    hands = [list(h) for h in start_hands]
    melds = [[] for _ in range(4)]
    draw_no = [0, 0, 0, 0]
    tenpai_at = [None] * 4
    hu_seat = None
    for e in events:
        t, seat = e.get("type"), e.get("seat")
        if seat is None:
            continue
        if t == "tile_drawn":
            tile = e.get("tile")
            if tile:
                hands[seat].append(tile)
                draw_no[seat] += 1
                e_cnt = len(melds[seat])
                g_cnt = sum(1 for m in melds[seat] if m.get("gang"))
                pre = list(hands[seat])
                if len(pre) == 14 - 3 * e_cnt - g_cnt and tenpai_at[seat] is None:
                    pre.pop()          # 摸前 13-3e-g
                    try:
                        s0 = S(pre, qidui=(e_cnt == 0 and g_cnt == 0),
                                exposed_melds=e_cnt, gangs=g_cnt)
                        if s0 == 0:
                            tenpai_at[seat] = draw_no[seat]
                    except ValueError:
                        pass
        elif t == "tile_discarded":
            tile = e.get("tile")
            if tile and tile in hands[seat]:
                hands[seat].remove(tile)
        elif t == "chi":
            got = (e.get("data") or {}).get("tiles") or []
            for x in got:
                if x != e.get("tile") and x in hands[seat]:
                    hands[seat].remove(x)
            melds[seat].append({"chi": True, "gang": False})
        elif t == "peng":
            for _ in range(2):
                if e.get("tile") in hands[seat]:
                    hands[seat].remove(e.get("tile"))
            melds[seat].append({"chi": False, "gang": False})
        elif t == "gang":
            kind = (e.get("data") or {}).get("kind")
            tl = e.get("tile")
            if kind == "bu":
                if tl in hands[seat]:
                    hands[seat].remove(tl)
                for m in melds[seat]:
                    if not m.get("gang") and m.get("tile") == tl:
                        m["gang"] = True
                        break
            elif kind == "an":
                for _ in range(4):
                    if tl in hands[seat]:
                        hands[seat].remove(tl)
                melds[seat].append({"chi": False, "gang": True, "tile": tl})
            else:
                for _ in range(3):
                    if tl in hands[seat]:
                        hands[seat].remove(tl)
                melds[seat].append({"chi": False, "gang": True, "tile": tl})
        elif t == "round_ended":
            hu_seat = e.get("seat")
            break
    return hu_seat, tenpai_at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    files = sorted(glob.glob("var/replays/server/*.json"))
    if args.limit:
        files = files[: args.limit]
    # 聚合键：user_id（seats 映射）；列 = [席局, 胡, 听牌首次巡和, 听牌次数,
    # 胡局听牌巡和]
    agg = {}
    names = {}
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        seats = d.get("seats") or []
        uid_of = {i: (s.get("user_id"), s.get("name"))
                  for i, s in enumerate(seats)}
        for i, s in enumerate(seats):
            names.setdefault(s.get("user_id"), s.get("name"))
        for rn, dealer, start_hands, evs in _rounds(d):
            if not start_hands or len(start_hands) != 4:
                continue
            hu, ta = run_round(start_hands, evs, dealer)
            for seat in range(4):
                uid = uid_of.get(seat, ("?", "?"))[0]
                a = agg.setdefault(uid, [0, 0, 0, 0, 0])
                a[0] += 1
                a[1] += 1 if hu == seat else 0
                if ta[seat] is not None:
                    a[2] += ta[seat]
                    a[3] += 1
                    if hu == seat:
                        a[4] += ta[seat]
    print("%-28s %6s %6s %7s %7s %7s" %
          ("name", "席局", "胡", "胡率%", "听牌率%", "均听巡"))
    for uid, a in sorted(agg.items(), key=lambda kv: -kv[1][1] / max(1, kv[1][0])):
        n, hu, ts, tc, hw = a
        print("%-28s %6d %6d %7.1f %7.1f %7.2f" %
              ((names.get(uid) or uid)[:28], n, hu, 100.0 * hu / max(1, n),
               100.0 * tc / max(1, n), ts / max(1, tc)))


if __name__ == "__main__":
    main()
