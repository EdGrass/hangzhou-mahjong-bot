# -*- coding: utf-8 -*-
"""SpeedC163 —— **路线 × 副露组合臂**：c159 的分时段压对数 + c156 的学习副露补加。

这不是第三个独立旋钮，而是当前仅有的两个真候选的组合：
  · `_pick_discard` ← SpeedC159：按河长分时段压多对子，弃后对数贴近强玩家；
  · `_want_claim`  ← SpeedC156：质量门控拒绝窗口上的单向学习补加，覆盖强玩家实际吃碰；
  · C036 / c150 束仍由继承链保留，绝不旁路。

MRO：SpeedC163 → SpeedC159 → SpeedC156 → SpeedC151 → SpeedC150 → ...
  因此 c159 的出牌钩子与 c156 的副露钩子各取其一，且两者的 `super()` 仍沿正确链工作。
"""
from __future__ import annotations

from .speedc156 import SpeedC156
from .speedc159 import SpeedC159


class SpeedC163(SpeedC159, SpeedC156):
    def __init__(self, name="speedc163"):
        super().__init__(name)
