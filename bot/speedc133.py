# -*- coding: utf-8 -*-
"""SpeedC133 —— `speedc132`（进张优先弃牌）+ **自杠**（`SELF_GANG=True`）的组合候选。

用途：如果 C132（进张）先被 A/B 判定采用，则下一个要单独测的就是自杠；
本类把两者合起来，供「C132 已上线后」的直接升级测试。**不要在 C132 未验证时先测本类**
（那样一次动两个变量，结果无法归因）。
"""
from __future__ import annotations

from .speedc132 import SpeedC132


class SpeedC133(SpeedC132):
    SELF_GANG = True

    def __init__(self, name="speedc133"):
        super().__init__(name)
