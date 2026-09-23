# -*- coding: utf-8 -*-
"""SpeedC166 —— **快版组合**：c164 的轻量分时段路线 + c165 的学习副露。"""
from __future__ import annotations

from .speedc164 import SpeedC164
from .speedc165 import SpeedC165


class SpeedC166(SpeedC164, SpeedC165):
    def __init__(self, name="speedc166"):
        super().__init__(name)
