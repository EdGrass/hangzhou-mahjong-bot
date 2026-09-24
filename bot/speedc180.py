# -*- coding: utf-8 -*-
"""SpeedC180 —— 终极 false 配置候选：c165 学习副露 + c147（BC + c136 + c144/c141）。"""
from __future__ import annotations

from .speedc147 import SpeedC147
from .speedc165 import SpeedC165


class SpeedC180(SpeedC165, SpeedC147):
    def __init__(self, name="speedc180"):
        super().__init__(name)
