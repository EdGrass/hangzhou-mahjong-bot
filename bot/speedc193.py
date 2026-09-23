# -*- coding: utf-8 -*-
"""SpeedC193 —— speedtugc + **仅做庄时**启用 c151 的压对数路线。

动机：二测强场证明 c151 的全局路线项失败；但庄胡收入占价值缺口约 67%，
做庄时早听、连庄的结构价更高。本候选只在 `dealer == seat` 时调用 c151 的
`_pick_discard_route`，做闲时严格回退 speedtugc 的 `_best_discard_t`。
不继承 c151 的其它任何层。
"""
from __future__ import annotations

from .speedc151 import _pick_discard_route
from .speedt import _best_discard_t
from .speedtugc import SpeedTUGC


class SpeedC193(SpeedTUGC):

    def __init__(self, name="speedc193"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        try:
            dealer = (view or {}).get("dealer")
            seat = (view or {}).get("seat")
            is_dealer = bool(isinstance(dealer, int) and dealer == seat)
        except Exception:
            is_dealer = False
        if is_dealer:
            return _pick_discard_route(hand, drawn, exposed, gangs,
                                       god_meld=self.GOD_MELD, view=view)
        return _best_discard_t(hand, drawn, exposed, gangs,
                               god_meld=self.GOD_MELD)
