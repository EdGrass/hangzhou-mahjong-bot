# -*- coding: utf-8 -*-
"""SpeedC178 —— fast c136 质量副露 + c144 明/自杠 + c141 财飘修正。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc177 import SpeedC177


class SpeedC178(SpeedC144, SpeedC141, SpeedC177):
    SELF_GANG = True

    def __init__(self, name="speedc178"):
        super().__init__(name)
