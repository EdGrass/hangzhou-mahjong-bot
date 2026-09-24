# -*- coding: utf-8 -*-
"""Pair-KEEPING bias: the untested sign of the ROUTE_BONUS axis.

Evidence chain (all measured on real portal replays, same rooms):
  * `var/_midgame_strat.py`: conditional on the meld count held at turn k, our mean
    shanten equals the strong players' (1 meld: 0.58 vs 0.52; 2 melds: 0.27 vs 0.25)
    -- once we have melded, we are NOT slower.  The lag is that we meld far less:
    at k=8, 47.9% of our draws are still door-clean vs 34.2% for top-32, and 2+
    melds 15.6% vs 27.8%.
  * `var/_meld_quality_compare.py`: they take 2.6x more flat (equal-shanten) melds,
    and those melds are better (+15.80 vs +12.31 mean delta-ukeire).
  * `var/_meld_type_mix.py`: our chi/peng MIX is identical (53.8% vs 52.0% chi) --
    we are short on both kinds, not biased to one.
  * R949: at turn 7+ we hold >=3 pairs 7.5% of the time vs 25.2% for the leaders.
    Pairs are the peng resource.

`speedc151` scores a discard as u = real_ukeire + ROUTE_BONUS * 1{pairs <= 2} with
ROUTE_BONUS = +8.0 -- i.e. it pays up to 8 live tiles to REDUCE the pair count
(measured cost: 2.47 live tiles on the 7.5% of decisions where it fires, see
`var/_routebonus_cost.py`).  Loosening/zeroing that direction (bonus 2 / bonus 0)
tested flat on the rollout, so the axis is live but the +8 side is unproven.

This module walks the SAME axis the other way: a negative bonus rewards keeping
3+ pairs, i.e. preserving meld material.  Everything else is byte-identical to
`speedc151` (same copied scoring path, same `_pref`/drawn tie-breaks).
"""
from __future__ import annotations

import time

from .speedc150 import SpeedC150
from .speedroute import _pick_discard_route_bonus


class _RouteKeepBase(SpeedC150):
    ROUTE_BONUS = -8.0

    def __init__(self, name="speedroutekeep"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_route_bonus(
            hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
            deadline=None, fallback=None,
            route_bonus=self.ROUTE_BONUS,
            gate_river=self.GATE_RIVER)


class SpeedRouteKeep4(_RouteKeepBase):
    ROUTE_BONUS = -4.0
    GATE_RIVER = 0

    def __init__(self, name="speedroutekeep4"):
        super().__init__(name)


class SpeedRouteKeep8(_RouteKeepBase):
    ROUTE_BONUS = -8.0
    GATE_RIVER = 0

    def __init__(self, name="speedroutekeep8"):
        super().__init__(name)


class SpeedRouteKeep8Late(_RouteKeepBase):
    """Pair-keeping only after the river reaches 12 (mid/late hand)."""

    ROUTE_BONUS = -8.0
    GATE_RIVER = 12

    def __init__(self, name="speedroutekeep8late"):
        super().__init__(name)


#: `_RouteKeepBase` needs a default for the base class itself
_RouteKeepBase.GATE_RIVER = 0
