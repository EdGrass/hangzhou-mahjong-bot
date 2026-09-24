# -*- coding: utf-8 -*-
"""SpeedC181 —— 终极 true 配置候选：c180 + YouCaiBiKao 闸门 + 被拦后转爆头。"""
from __future__ import annotations

from .speedc147 import SpeedC147
from .speedc165 import SpeedC165
from .ycbk_fast import FastYCBKForceMixin


class SpeedC181(FastYCBKForceMixin, SpeedC165, SpeedC147):
    def __init__(self, name="speedc181"):
        super().__init__(name)
