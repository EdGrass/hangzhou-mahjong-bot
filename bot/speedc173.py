# -*- coding: utf-8 -*-
"""SpeedC173 —— fast route c164 + c144 明/自杠 + c141 财飘修正。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc164 import SpeedC164


class SpeedC173(SpeedC144, SpeedC141, SpeedC164):
    SELF_GANG = True

    def __init__(self, name="speedc173"):
        super().__init__(name)
