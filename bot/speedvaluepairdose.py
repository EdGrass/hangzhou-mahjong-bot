# -*- coding: utf-8 -*-
"""Pair-penalty DOSE series on top of `SpeedValue` (calibration arm for the pair axis).

Why a dose series: the leaderboard top32 sits BETWEEN our two historical settings --
  * c151 (full ROUTE_BONUS tie-break)  -> realised mean pairs 2.33, >=3 pairs 30%
  * tugc (no pair incentive at all)    -> realised mean pairs 2.71, >=3 pairs 59%
  * top32                              -> realised mean pairs 2.48, >=3 pairs 48%
and `SpeedValue` (no penalty at all) already moves us one step toward the top
(measured on 250 real windows: mean 2.25 -> 2.31, >=3 pairs 27.8% -> 33.5%).

⚠ Calibration fact (measured): `SpeedValuePenalty`'s 0.64 points is NOT "a quarter" of
c151's incentive -- in the additive V model it lands at mean **2.20 / 22.9%**, i.e.
STRONGER than c151 (2.25 / 27.8%).  So the useful middle doses are 0.16 and 0.32
(= 2 and 4 live-tile equivalents at W_UKEIRE[1] = 0.080 points/tile).

Use: only if a campaign on pure `SpeedValue` overshoots the pair profile upward.
"""
from __future__ import annotations

from .speedvalue import SpeedValue


class _PairDose(SpeedValue):
    PAIR_BONUS_POINTS = 0.0       # extra V points for a discard leaving <= 2 pairs

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None or not self.PAIR_BONUS_POINTS:
            return v
        try:
            import collections as _c
            pc = sum(1 for n in _c.Counter(rem).values() if n >= 2)
        except Exception:
            return v
        if pc <= 2:
            v += self.PAIR_BONUS_POINTS
        return v


class SpeedValuePair2(_PairDose):
    """~2 live-tile equivalents of "keep the pair count low" (weak dose)."""
    PAIR_BONUS_POINTS = 0.16

    def __init__(self, name="speedvaluepair2"):
        super().__init__(name)


class SpeedValuePair4(_PairDose):
    """~4 live-tile equivalents (medium dose)."""
    PAIR_BONUS_POINTS = 0.32

    def __init__(self, name="speedvaluepair4"):
        super().__init__(name)


class _PairReward(SpeedValue):
    """Positive dose: reward discards that leave >= 3 pairs (the top32 direction)."""
    PAIR_REWARD_POINTS = 0.0

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None or not self.PAIR_REWARD_POINTS:
            return v
        try:
            import collections as _c
            pc = sum(1 for n in _c.Counter(rem).values() if n >= 2)
        except Exception:
            return v
        if pc >= 3:
            v += self.PAIR_REWARD_POINTS
        return v


class SpeedValuePairR2(_PairReward):
    """+0.16 points (~2 live tiles) for keeping >=3 pairs."""
    PAIR_REWARD_POINTS = 0.16

    def __init__(self, name="speedvaluepairr2"):
        super().__init__(name)


class SpeedValuePairR4(_PairReward):
    """+0.32 points (~4 live tiles)."""
    PAIR_REWARD_POINTS = 0.32

    def __init__(self, name="speedvaluepairr4"):
        super().__init__(name)


class SpeedValuePairR8(_PairReward):
    """+0.64 points -- same magnitude as the (strong) 0.64 penalty."""
    PAIR_REWARD_POINTS = 0.64

    def __init__(self, name="speedvaluepairr8"):
        super().__init__(name)
