# -*- coding: utf-8 -*-
"""C117N：**纯 ukeire 弃牌基线**（无学生网），用于把「tie-break 进张优先」与「网」两个因素分离。
背景：C117（ukeire 基线 + 网）sim 配对 -52/房，但可能被「网在新基线下相对特征失真」污染。
"""
from __future__ import annotations

from .speedtugc import SpeedTUGC
from .speedc117 import _best_discard_u
from . import speedc067 as _c067
from .model import my_turn, window_pending


class C117NPolicy(SpeedTUGC):
    def __init__(self, name="speedc117n"):
        super().__init__(name=name)

    def decide(self, view):
        old = _c067._best_discard_t
        _c067._best_discard_t = _best_discard_u
        try:
            return super().decide(view)
        finally:
            _c067._best_discard_t = old
