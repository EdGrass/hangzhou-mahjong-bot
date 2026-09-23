# -*- coding: utf-8 -*-
"""SpeedC184 —— 终极启发式 true 候选：c183 + YouCaiBiKao 闸门 + 被拦后转爆头。"""
from __future__ import annotations

from .speedc136 import SpeedC136
from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc164 import SpeedC164
from .speedc165 import SpeedC165
from .ycbk_fast import FastYCBKForceMixin


class SpeedC184(FastYCBKForceMixin, SpeedC144, SpeedC141, SpeedC165, SpeedC136, SpeedC164):
    SELF_GANG = True

    def __init__(self, name="speedc184"):
        super().__init__(name)
