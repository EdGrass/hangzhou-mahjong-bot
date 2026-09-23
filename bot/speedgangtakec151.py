# -*- coding: utf-8 -*-
# Isolated version of the gang fix: c151 + "take the gangs" only.
# Same rationale as bot/speedgangtake.py, but without the value model, so the
# arena can measure the gang effect on top of the INCUMBENT arm alone.
from __future__ import annotations

from .speedc151 import SpeedC151


class SpeedGangTakeC151(SpeedC151):
    SELF_GANG = True

    def __init__(self, name="speedgangtakec151"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if kind == "gang_ming":
            try:
                river_len = len(view.get("river") or [])
            except Exception:
                river_len = 0
            if river_len >= int(self.SELF_GANG_MAX_RIVER):
                return False
            return True
        return super()._want_claim(view, kind, pair)
