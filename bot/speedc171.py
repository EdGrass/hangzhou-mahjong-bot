# -*- coding: utf-8 -*-
"""SpeedC171 —— 快版 c166（路线+副露组合）+ YouCaiBiKao 合法胡闸门。"""
from __future__ import annotations

from .speedc166 import SpeedC166
from .ycbk_fast import FastYCBKMixin


class SpeedC171(FastYCBKMixin, SpeedC166):
    def __init__(self, name="speedc171"):
        super().__init__(name)
