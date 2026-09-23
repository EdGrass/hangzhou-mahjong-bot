# -*- coding: utf-8 -*-
"""SpeedC174 —— fast meld c165 + c144 明/自杠 + c141 财飘修正。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc165 import SpeedC165


class SpeedC174(SpeedC144, SpeedC141, SpeedC165):
    SELF_GANG = True

    def __init__(self, name="speedc174"):
        super().__init__(name)
