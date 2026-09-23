# -*- coding: utf-8 -*-
"""SpeedC185 —— **真版 true 候选**：c156 + YouCaiBiKao 合法胡闸门 + 被拦后转爆头。

为什么（2026-09-17）：
- `c184` 是"快版近似"路线的 true 候选（= c183 + 闸门），而 `c183 = c164 route + c165 学习副露
  + c136 质量副露 + c144/c141`；谱系核对后 **c150 = C146(明杠+自杠+质量副露+财飘) + C135(真进张)**，
  `c151/c156` 才是这些机制的**真身** ⇒ c184 严格说是一份代理的真身 + 闸门。
- 2026-09-17 `real_ukeire` 尾延迟修复后，真版 c151/c156/c159 已过 M=10 门禁
  （c151 draw max 356ms / c156 326ms / c159 494ms，0 超 3s）⇒ 没有理由 true 配置还用代理。

本臂 = `SpeedC156`（c151 路线 + 学习选择性副露）**只加**合法闸门：
  · `FastYCBKMixin`：拦下 YouCaiBiKao=false 语义下的非法平胡（白板财神平胡/七对）；
  · `FORCE_BAOTOU_ON_BLOCK=True`：被拦后用 `_best_giveup` 转爆头（与 c184/c176 同一策略）。
**唯一差别就是闸门**：不出现"该胡却被拦"的场合时，`decide()` 与 c156 逐条相同（有单测钉死）。
"""
from __future__ import annotations

from .speedc156 import SpeedC156
from .ycbk_fast import FastYCBKForceMixin


class SpeedC185(FastYCBKForceMixin, SpeedC156):
    """真版 true 候选（c156 + 合法胡闸门 + 转爆头）。SELF_GANG 由 C146 继承为 True。"""

    def __init__(self, name="speedc185"):
        super().__init__(name)
