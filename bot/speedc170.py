# -*- coding: utf-8 -*-
"""SpeedC170 —— 快版 c165（学习副露）+ YouCaiBiKao 合法胡闸门。"""
from __future__ import annotations

from .speedc165 import SpeedC165
from .ycbk_fast import FastYCBKMixin


class SpeedC170(FastYCBKMixin, SpeedC165):
    def __init__(self, name="speedc170"):
        super().__init__(name)
