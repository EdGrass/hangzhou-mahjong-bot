# -*- coding: utf-8 -*-
# Take the gangs: each one DOUBLES the fan, and this game has no ron risk.
#
# Structural facts (both verified):
#   * mahjong/fan.py: total fan = branch x 2^(chain actions) x (4-white x2) x (baotou x2)
#     i.e. EVERY gang (and every cai-piao) multiplies the whole score by 2.
#   * The game is tsumo-only (R996: no `hu` event in 54,581 rounds), so there is
#     no qiang-gang risk to weigh against taking a gang.
#   * Real replays: the leaders gang 0.0375-0.0887 per round while our family is
#     documented as having NO self-gang path at all
#     (SpeedTUGC.SELF_GANG = False, bot/speedtugc.py:65-68), and a ming-gang can
#     essentially never satisfy the "shanten must strictly drop" gate -- so both
#     routes are effectively shut.
#   * Our own decision log: at 426 windows where a ming-gang was LEGAL we ganged
#     only 38.3% and PASSED 52.3% (var/_gang_opportunity.py).
#
# What this arm changes, relative to SpeedValue (the current best candidate):
#   1. SELF_GANG = True -- enables the already-written 暗杠/补杠 path in
#      SpeedTUGC._maybe_gang (that path weighs the 七对 route cost and a wall
#      guard, but never counted the x2 fan either).
#   2. _want_claim accepts a legal ming-gang whenever the wall guard allows,
#      instead of routing it through the shanten-drop gate.
#
# The wall guard reuses SELF_GANG_MAX_RIVER (56), a conservative proxy for the
# server rule "no gang in the last 10 draws" (at river=56 the wall still holds
# ~28 tiles vs the server's 22-tile minimum).
from __future__ import annotations

from .speedvalue import SpeedValue


class SpeedGangTake(SpeedValue):
    SELF_GANG = True

    def __init__(self, name="speedgangtake"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if kind == "gang_ming":
            try:
                river_len = len(view.get("river") or [])
            except Exception:
                river_len = 0
            if river_len >= int(self.SELF_GANG_MAX_RIVER):
                return False            # near the wall end: server bans gangs
            return True
        return super()._want_claim(view, kind, pair)
