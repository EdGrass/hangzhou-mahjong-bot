# -*- coding: utf-8 -*-
# Baotou-path term: reward progress toward the "4 melds + 白" shape.
#
# Evidence (R1011/R1013, real replays):
#   * 爆头 appears in 23.5% of our wins vs 27.9% of the leaders' (x2 fan AND it
#     means "any draw wins" -- it guarantees conversion).
#   * P(爆头 | winner's meld count) = 19.7% (0 melds) -> 28.6% (1) -> 46.1% (2)
#     -> 71.4% (3), i.e. baotou comes almost only from the MELDED route, because
#     the shape is "4 completed melds + 白".
#   * We are behind the leaders only in the 0- and 1-meld cells (-3.7pp / -2.8pp)
#     and our winning mix is 68.9% meld-free vs their 63.1%.
#   * The two existing carriers both fail: `speedc131` (god_meld=False) LOWERS
#     baotou (9.3% vs 11.4%, R1012) and loosening the claim gate is clearly
#     harmful (R977).  So the lever must price the PATH, not relax a threshold.
#
# Mechanism: when the hand still holds 白, add W_PATH_GROUP points per completed
# group (exposed melds + concealed triplets).  Five groups' worth of progress
# therefore outweighs roughly one fan, which is the right order given the
# fitted exchange rate (1 fan ~ 2.4 points at tenpai).
from __future__ import annotations

from collections import Counter

from .speedc151 import SpeedC151
from .speedvalue import SpeedValue


class _BaotouPathMixin:
    W_PATH_GROUP = 0.6          # points per completed group, while holding 白

    def _path_bonus(self, rem, exposed):
        try:
            if "白" not in rem:
                return 0.0
            triplets = sum(1 for n in Counter(rem).values() if n >= 3)
            groups = int(exposed or 0) + triplets
            return self.W_PATH_GROUP * groups
        except Exception:
            return 0.0

    def value_of(self, rem, e, g, vis, view, sh):
        v = super().value_of(rem, e, g, vis, view, sh)
        if v is None:
            return None
        return v + self._path_bonus(rem, e)


class SpeedBaotouPath(_BaotouPathMixin, SpeedValue):
    """Baotou-path term on top of the value policy."""

    def __init__(self, name="speedbaotoupath"):
        super().__init__(name)


class SpeedBaotouPathC151(_BaotouPathMixin, SpeedC151):
    """Isolated: c151 + the baotou-path term only.

    c151 has no `value_of`, so the term is applied by subclassing and overriding
    `_pick_discard` is unnecessary -- instead we express it as an extra tie-break
    weight on top of c151's own key via a thin wrapper (see _pick_discard).
    """

    def __init__(self, name="speedbaotoupathc151"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        # No value function to modify here: the isolated variant is built in
        # bot/speedbaotoupick.py (which scores all min-shanten discards).
        return base


class SpeedBaotouPathStrong(_BaotouPathMixin, SpeedValue):
    """Dose test: x5 the path weight (3.0 points per completed group).

    The defensible weight (0.6/group) only flipped 0.3% of decisions, i.e. below
    the arena's resolving power.  This variant exists purely to ask whether the
    MECHANISM carries any signal at all when it actually fires.
    """

    W_PATH_GROUP = 3.0

    def __init__(self, name="speedbaotoupathstrong"):
        super().__init__(name)
