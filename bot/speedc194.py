# -*- coding: utf-8 -*-
"""SpeedC194 —— 中盘“3+ 对子”外科式拆对（基座 speedtugc）。

背景：强场听牌差距从 k5 起扩大；项目已证 3~4 对时听牌率显著下降，
但 c151 的全局压对数路线在强场失败。本候选只在中盘（river_len 12~28）
且基线弃牌后仍 >=3 对时，寻找同向听、减对子、真进张损失不超过 TOL 的替代弃牌。
其余 100% 继承 speedtugc。
"""
from __future__ import annotations

import collections

from mahjong.shanten_exact import shanten as exact_shanten

from .speedt import _best_discard_t, _pref
from .speedtugc import SpeedTUGC
from .ukeire import real_ukeire, visible_counts

MID_LO = 12
MID_HI = 28
TOL = 4.0
MAX_PAIRS = 2


def _pairs(rem):
    return sum(1 for v in collections.Counter(rem).values() if v >= 2)


class SpeedC194(SpeedTUGC):

    def __init__(self, name="speedc194", tol=TOL, mid_lo=MID_LO, mid_hi=MID_HI):
        super().__init__(name)
        self.tol = float(tol)
        self.mid_lo = int(mid_lo)
        self.mid_hi = int(mid_hi)
        self.stats = collections.Counter()

    def _metrics(self, hand, d, exposed, gangs, vis):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
            u = 0.0
            if s > 0:
                u = float(real_ukeire(rem, exposed=exposed, gangs=gangs,
                                      visible=vis)[0] or 0)
        except Exception:
            return None
        return s, u, _pairs(rem)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = _best_discard_t(hand, drawn, exposed, gangs,
                               god_meld=self.GOD_MELD)
        try:
            river_len = int((view or {}).get("river_len") or len((view or {}).get("river") or []))
        except Exception:
            river_len = 0
        if not (self.mid_lo <= river_len <= self.mid_hi):
            return base
        self.stats["mid"] += 1
        vis = visible_counts(hand, river=(view or {}).get("river"),
                             all_melds=(view or {}).get("all_melds"))
        bm = self._metrics(hand, base, exposed, gangs, vis)
        if bm is None or bm[2] <= MAX_PAIRS:
            self.stats["base_not_multi"] += 1
            return base
        self.stats["base_multi"] += 1
        sb, ub, pb = bm
        best = None
        for d in sorted(set(hand)):
            m = self._metrics(hand, d, exposed, gangs, vis)
            if m is None:
                continue
            s, u, pc = m
            if s != sb or pc >= pb or pc > MAX_PAIRS:
                continue
            if u + self.tol < ub:
                continue
            key = (-u, pc, _pref(d, hand), -1 if d == drawn else 0, d)
            if best is None or key < best[0]:
                best = (key, d)
        if best is not None:
            self.stats["changed"] += 1
            return best[1]
        self.stats["no_safe"] += 1
        return base
