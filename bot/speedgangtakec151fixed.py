# -*- coding: utf-8 -*-
"""SpeedGangTakeC151Fixed = c151 + take-gangs + gang-hand discard P0 fix.

Why this file exists (2026-09-23):
  * bot/speedgangtakefixed.py  = SpeedValue + gang  ⇒ bundling TWO axes.
  * bot/speedgangtakec151.py   = c151 + gang (no gang-hand discard fix) ⇒ single
    axis but the P0 discard bug (cands empty -> hand[0]) suppresses what extra
    gangs buy (R1016: 0.38% of discards in gang-hand state).
  This arm = the incumbent arm (c151) + ONLY the gang changes (take ming/self gang
  + gang-aware discard chooser), i.e. a clean single-variable candidate for a
  campaign whose baseline is c151.
"""
from __future__ import annotations

from .speedgangfix import _pick_discard_route_gangaware
from .speedgangtakec151 import SpeedGangTakeC151


class SpeedGangTakeC151Fixed(SpeedGangTakeC151):
    def __init__(self, name="speedgangtakec151fixed"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if gangs:
            return _pick_discard_route_gangaware(
                hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
                route_bonus=0.0, gate_river=0)
        return super()._pick_discard(hand, drawn, exposed, gangs, view=view)