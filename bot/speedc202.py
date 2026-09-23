# -*- coding: utf-8 -*-
"""SpeedC202 —— c135 的**加权目标**候选：把"待ち形状（両面数）"从并列项提升为**显式权重项**。

为什么需要：R545 实测 c200/c201 那种"并列项"只改了 **1.1% / 2.6%** 的决策 ⇒ **实验是死的**，
"没效果"不能说明机制无效。本候选用 `score = u1 + λ·ryanmen`，λ 由环境变量控制，
先把**分歧率调到 20~40%**（真正的干预），再用 `_rollout_win.py` 测和了率。
"""
from __future__ import annotations
import collections, os
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts


def _ryanmen(h13):
    c = collections.Counter(h13)
    n = 0
    for suit in "wbt":
        for i in range(2, 8):
            if (str(i) + suit) in c and (str(i + 1) + suit) in c:
                n += 1
    return n


class SpeedC202(SpeedTUGC):
    LAMBDA = float(os.environ.get("C202_LAMBDA", "2"))

    def __init__(self, name="speedc202"):
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
            score = u1 + self.LAMBDA * _ryanmen(rem)
            key = (s, -wcnt, -score, _pref(d, hand), -1 if d == drawn else 0)
            if best_key is None or key < best_key: best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
