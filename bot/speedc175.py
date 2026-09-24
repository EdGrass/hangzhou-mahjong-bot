# -*- coding: utf-8 -*-
"""SpeedC175 —— fast combo c166 + c144 明/自杠 + c141 财飘修正。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc166 import SpeedC166


class SpeedC175(SpeedC144, SpeedC141, SpeedC166):
    SELF_GANG = True

    def __init__(self, name="speedc175"):
        super().__init__(name)
