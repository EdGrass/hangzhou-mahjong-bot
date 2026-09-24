# -*- coding: utf-8 -*-
# Take the gangs AND fix the gang-hand discard path (R1016's P0 bug).
#
# Why bundle these two: taking more ming-gangs is the only new line that leans
# positive on BOTH bases (R1017: c151-gangtakec151 = -2.47, gangtake-speedvalue =
# +2.41 per seat-8-rounds, both t~1.0-1.2), but the arms that take more gangs also
# spend more decisions in the gang-hand state -- and R1016 measured that state to
# hit the R939 P0 bug (cands empty -> `return hand[0]`) on 0.38% of all discards.
# So the two changes are entangled: more gangs amplify the bug, and the bug
# suppresses whatever the extra gangs buy.
#
# Implementation: gangs == 0 -> pure SpeedGangTake (the V policy); gangs > 0 ->
# the gang-aware chooser from bot/speedgangfix.py (same as SpeedLookaheadTUGC does).
from __future__ import annotations

from .speedgangfix import _pick_discard_route_gangaware
from .speedgangtake import SpeedGangTake


class SpeedGangTakeFixed(SpeedGangTake):
    def __init__(self, name="speedgangtakefixed"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if gangs:
            return _pick_discard_route_gangaware(
                hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
                route_bonus=0.0, gate_river=0)
        return super()._pick_discard(hand, drawn, exposed, gangs, view=view)
