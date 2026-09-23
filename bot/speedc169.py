# -*- coding: utf-8 -*-
"""SpeedC169 —— 快版 c164（分时段压对数）+ YouCaiBiKao 合法胡闸门。"""
from __future__ import annotations

from .speedc164 import SpeedC164
from .ycbk_fast import FastYCBKMixin


class SpeedC169(FastYCBKMixin, SpeedC164):
    def __init__(self, name="speedc169"):
        super().__init__(name)
