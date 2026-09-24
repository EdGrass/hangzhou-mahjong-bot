# -*- coding: utf-8 -*-
"""`bot/speedvaluepost.py` —— 役 3 的 **speedvalue 分支**隔离臂。

## 为什么需要它（R1141 的教训 + R1166 的缺口）

役 3 的目标缺口是**听牌率**（我们 vs top32：53.0% vs 59.4%，−6.44pp；其中
"副露 2+ 时"最严重：54.3% vs 66.9%）。对应机制件是 `bot/speedmeldpost.py`：
"claim gate 是按**副露后最优弃牌**接受碰/吃的，但实际弃牌选择器带着路线加成、
对子偏好与 `_pref` 平局键，**有时把副露换来的增益扔掉**"。

但 `SpeedMeldPost` **派生自 `SpeedC151`**。若役 2 判"采用 speedvalue"，则
"c151+meldpost"相对新基线 speedvalue 就是**两条轴的组合**（出牌轴 + 副露轴）
⇒ 判词无法归因（R1141 已在杠轴上踩过同一个坑，当时新建了 `speedgangtakec151fixed`）。

## 本臂（单变量，相对 **SpeedValue**）

MRO = `SpeedValuePost → SpeedMeldPost → SpeedValue → SpeedC151 → …`

- `SpeedMeldPost._pick_discard` 是**装饰器**：先取 `super()._pick_discard(...)`（在本 MRO 下
  = **SpeedValue 的拟合 V 出牌器**），**仅当** claim gate 自己的判据
  `(shanten, -real_ukeire)` **严格更优**时才改打那张牌；平局一律保留 SpeedValue 的 `_pref`。
- 作用域同样只有"**自己副露后的第一次弃牌**"（`drawn is None and exposed >= 1` 且长度吻合），
  其余 100% 沿用 SpeedValue。

⇒ 相对 `SpeedValue` 的**唯一差别 = 副露后弃牌保真**这一条 ⇒ 满足单变量预登记。
（役 2 若不采用 speedvalue，则走 c151 分支：直接用现成的 `speedmeldpost`。）
"""
from __future__ import annotations

from .speedmeldpost import SpeedMeldPost
from .speedvalue import SpeedValue


class SpeedValuePost(SpeedMeldPost, SpeedValue):
    def __init__(self, name="speedvaluepost"):
        super().__init__(name)
