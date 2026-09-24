# -*- coding: utf-8 -*-
"""C020 SpeedTV —— SpeedTU + 按「剩余张数」评估听牌（活等）。

动机（2026-09-10 真机实测）：
- 房 a_124fc976b032 中我方「最先听牌」占比 31.2%（已超冠军池 22.9%），但
  **最先听牌时胡率仅 46.2% vs 冠军 57.4%**，而两者「之后还可摸」都只有 1.50 次
  → 差距不在速度、在**听牌宽度**；
- 首次听牌的**活等副本数**：我方 7.77 vs 冠军 9.31（少 17%）；基线口径同样
  8.39 vs 9.72；
- 现有 `_best_discard_t` 的次键是 `len(waits(...))` = **牌种数**，不区分
  「4 种各剩 1 张」与「2 种各剩 4 张」。

与 SpeedTU 的唯一差异 = 弃牌次键：把「等待牌种数」换成「等待牌的剩余张数」
（剩余 = 4 − 本人手牌 − 公开弃牌河 − 本人副露；已知口径保守：河与副露对
被副露走的那张会重复计数，故略偏悲观）。
其余 100% 继承 SpeedTU（听牌升级副露 / SpeedT 出牌 / SpeedE 胡与抓打圈）。
"""
from __future__ import annotations

import collections

from mahjong.hu import is_baotou, is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedt import _pref
from .speedtu import SpeedTU, _best_after_claim, want_claim_upgrade
from .speede import SpeedE


def _meld_tiles(m):
    """取副露牌面（兼容只有 tile 的旧形态）。"""
    ts = m.get("tiles")
    if ts:
        return list(ts)
    t = m.get("tile")
    if not t:
        return []
    n = 4 if m.get("type") == "gang" else 3
    return [t] * n


def _visible(hand, river, melds):
    c = collections.Counter()
    c.update(hand)
    c.update(river or [])
    for m in melds or []:
        c.update(_meld_tiles(m))
    return c


def _live_copies(wait_tiles, vis):
    return sum(max(0, 4 - vis.get(t, 0)) for t in wait_tiles)


def _best_discard_v(hand, drawn, exposed, gangs, river, melds,
                    god_meld=True):
    """弃牌：向听最小 → **等待剩余张数**最大 → SpeedT 弃牌偏好 → 保留刚摸。"""
    vis = _visible(hand, river, melds)
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
                wt = waits(rem, exposed_melds=exposed, gangs=gangs)
                live = _live_copies(wt, vis)
            except ValueError:
                live = 0
        key = (s, -live, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedTV(SpeedTU):
    def __init__(self, name="speedTV"):
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
                    tile = _best_discard_v(hand, drawn, exposed, gangs,
                                           view.get("river") or [], melds)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
