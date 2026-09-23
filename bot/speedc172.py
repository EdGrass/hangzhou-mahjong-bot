# -*- coding: utf-8 -*-
"""SpeedC172 —— c171 的强制版：合法胡被闸门拦下后，优先找能转爆头形的弃牌。"""
from __future__ import annotations

from .speedc166 import SpeedC166
from .ycbk_fast import FastYCBKForceMixin


class SpeedC172(FastYCBKForceMixin, SpeedC166):
    def __init__(self, name="speedc172"):
        super().__init__(name)
