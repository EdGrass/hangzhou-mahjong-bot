# -*- coding: utf-8 -*-
"""SpeedC183 —— 终极启发式 false 候选：c164 route + c165 学习副露 + c136 质量门控 + c144/c141。"""
from __future__ import annotations

from .speedc136 import SpeedC136
from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc164 import SpeedC164
from .speedc165 import SpeedC165


class SpeedC183(SpeedC144, SpeedC141, SpeedC165, SpeedC136, SpeedC164):
    SELF_GANG = True

    def __init__(self, name="speedc183"):
        super().__init__(name)
