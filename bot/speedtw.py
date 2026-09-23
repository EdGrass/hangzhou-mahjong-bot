# -*- coding: utf-8 -*-
"""C021 SpeedTW —— SpeedTU + 公开信息（四家副露 + 弃牌河）活等评估。

与 C020/SpeedTV 的差别（C020 真机 1 房未复现，判断为信息不足）：
- C020 只用了「自家手牌 + 弃牌河 + 自家副露」；
- C021 用上快照本来就带的**四家副露**（公开信息，此前 model.snap_view 只保留了
  本人那一家，其余三家被丢弃）+ 弃牌河 + 自家手牌 → 剩余张数估计更准。

动机数据（2026-09-10 真机）：最先听牌时「之后还可摸」双方都是 1.50 次，但
**首次听牌的活等副本 我方 7.77 vs 冠军 9.31** → 听牌宽度是听牌→胡转化
（45% vs 53-57%）的主要抓手。

口径：剩余 = 4 − (自家手牌 + 四家副露 + 弃牌河)，下限 0。
注意：被副露走掉的那张同时出现在「弃牌河」与「副露」里，会重复计 1 —— 属
保守方向（把该牌算得更难出），且四家一致，不改变候选间的相对排序。
其余 100% 继承 SpeedTU（听牌升级副露 / SpeedT 出牌 / SpeedE 胡与抓打圈）。
"""
from __future__ import annotations

import collections

from mahjong.hu import is_baotou, is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speedt import _pref
from .speedtu import SpeedTU


def _meld_tiles(m):
    ts = m.get("tiles")
    if ts:
        return list(ts)
    t = m.get("tile")
    if not t:
        return []
    return [t] * (4 if m.get("type") == "gang" else 3)


def _visible(hand, river, all_melds):
    c = collections.Counter()
    c.update(hand)
    c.update(river or [])
    for seat_melds in (all_melds or []):
        for m in seat_melds:
            c.update(_meld_tiles(m))
    return c


def _best_discard_w(hand, drawn, exposed, gangs, river, all_melds,
                    god_meld=True):
    """弃牌：向听最小 → **等待剩余张数（公开信息口径）**最大 → SpeedT 偏好 → 保留刚摸。"""
    vis = _visible(hand, river, all_melds)
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs,
                              god_meld=god_meld)
        except ValueError:
            continue
        live = 0
        if s == 0:
            try:
                live = sum(max(0, 4 - vis.get(t, 0))
                           for t in waits(rem, exposed_melds=exposed, gangs=gangs))
            except ValueError:
                live = 0
        key = (s, -live, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedTW(SpeedTU):
    def __init__(self, name="speedTW"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu and drawn:
                return {"action": "hu", "tile": ""}
            if hand:
                if view.get("god", {}).get("catch_play") and drawn:
                    return {"action": "discard", "tile": drawn}
                try:
                    tile = _best_discard_w(hand, drawn, exposed, gangs,
                                           view.get("river") or [],
                                           view.get("all_melds") or [])
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
