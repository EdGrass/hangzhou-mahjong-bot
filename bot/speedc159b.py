# -*- coding: utf-8 -*-
"""SpeedC159B —— c159 的**加力档**（同一旋钮：中盘 1.5、末盘 2.5）。

依据（STATUS §9.74 正确口径）：我方逐巡拆对率 T1..T8 = 4.8/1.0/1.5/2.3/3.4/4.9/6.2/7.2%，
强者 = 2.3/2.5/4.2/6.5/8.6/10.1/11.4/11.8% ⇒ **T2~T6 严重不足**，需要更强的中盘压对数。
（早盘仍为 0：正确口径显示我们 T1 反而偏高 4.8% vs 2.3%，不该再加早期压力。）
"""
from __future__ import annotations

from .speedc159 import SpeedC159, W_FORCE


class SpeedC159B(SpeedC159):

    WEIGHTS = W_FORCE

    def __init__(self, name="speedc159b"):
        super().__init__(name, weights=W_FORCE)
