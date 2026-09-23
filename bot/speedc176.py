# -*- coding: utf-8 -*-
"""SpeedC176 —— true 配置终极版：c175 fast 束 + YouCaiBiKao 闸门 + 被拦后转爆头。"""
from __future__ import annotations

from .speedc141 import SpeedC141
from .speedc144 import SpeedC144
from .speedc166 import SpeedC166
from .ycbk_fast import FastYCBKForceMixin


class SpeedC176(FastYCBKForceMixin, SpeedC144, SpeedC141, SpeedC166):
    SELF_GANG = True

    def __init__(self, name="speedc176"):
        super().__init__(name)
