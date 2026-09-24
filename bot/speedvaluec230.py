# -*- coding: utf-8 -*-
# Merge the two axes that R974/R976-R1013 identified as the gap: discard choice
# (speedvalue's fitted V) AND meld quality (c230's widest-chi rule).
#
# Why c230: R879 measured that our chi branch takes the FIRST pair passing the
# gate rather than the WIDEST -- of 13 windows with >=2 passable pairs, 5 (38%)
# took a non-widest option, the worst by 3.3x live tiles (14 vs 46).  R878 adds
# that our 1-shanten live count FALLS with melds (20.5 -> 20.0 -> 19.8) while the
# leaders' does not (22.6 -> 22.4 -> 22.7).  So the meld axis is about QUALITY,
# not about loosening the gate (which R977 showed is harmful).
#
# MRO note: SpeedValue and SpeedC230 both derive from SpeedC151.  Declaring
# `class SpeedValueC230(SpeedValue, SpeedC230)` puts SpeedValue's discard logic
# first and picks up SpeedC230._want_claim (SpeedValue does not define it); the
# zero-arg super() inside c230's hook then correctly resolves to SpeedC151.
from __future__ import annotations

from .speedc230 import SpeedC230
from .speedvalue import SpeedValue


class SpeedValueC230(SpeedValue, SpeedC230):
    def __init__(self, name="speedvaluec230"):
        super().__init__(name)
