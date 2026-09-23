# -*- coding: utf-8 -*-
"""SpeedC201 —— c135 + **両面优先**并列键（只在 u1 并列时生效）。

动机（R543/R544）：c135 的"到听牌 +4.7pp"被"听牌后活等张 −0.71 张 / 和了率只 +0.84pp"抵消。
麻将的经典解释是"贪进张数会做成 嵌張/単騎（窄待ち）"。本候选在 u1 **并列**时，
优先保留**両面（两面搭子）**最多的手形 —— 这是唯一还没试过、且直接对着"待ち宽度"的并列项。
"""
from __future__ import annotations
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts


def _ryanmen(h13):
    """两面搭子数：同花 n,n+1 且 n∈2..7（两侧都能进）。"""
    import collections
    c = collections.Counter(h13)
    n = 0
    for suit in "wbt":
        for i in range(2, 8):
            if (str(i) + suit) in c and (str(i + 1) + suit) in c:
                n += 1
    return n


class SpeedC201(SpeedTUGC):
    def __init__(self, name="speedc201"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        vis = None
        if view:
            try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            except Exception: vis = None
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try: s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0), exposed_melds=exposed, gangs=gangs)
            except Exception: continue
            cands.append((d, rem, s))
        if not cands: return hand[0]
        smin = min(c[2] for c in cands)
        best_key, best_tile = None, None
        for d, rem, s in cands:
            if s != smin: continue
            if s == 0:
                try: wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
                except Exception: wcnt = 0
                u1 = 0.0
            else:
                wcnt = 0
                try: u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
                except Exception: u1 = 0.0
            key = (s, -wcnt, -u1, -_ryanmen(rem), _pref(d, hand), -1 if d == drawn else 0)
            if best_key is None or key < best_key: best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
