# -*- coding: utf-8 -*-
"""SpeedC179 —— c178 + YouCaiBiKao 合法闸门 + 被拦后转爆头（true 配置终极替代）。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc177 import SpeedC177
from .ycbk_fast import FastYCBKForceMixin


class SpeedC179(FastYCBKForceMixin, SpeedC144, SpeedC141, SpeedC177):
    SELF_GANG = True

    def __init__(self, name="speedc179"):
        super().__init__(name)
