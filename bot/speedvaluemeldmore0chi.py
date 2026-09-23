# -*- coding: utf-8 -*-
"""`SpeedValueMeldMore0Chi` —— 役 3 首选组合臂（若役 2 由 `speedvalue` 胜出）。

组合方式（MRO，不复制任何逻辑）：
  * 出牌轴 ← `SpeedValue`（拟合 V(state)：听牌处按"活等张 + 番"重排，去掉从未标定的
    ROUTE_BONUS 对子惩罚）—— 这是"同分并列的路线选择"这一唯一剩余自由度的候选；
  * 副露轴 ← `SpeedMeldMore0Chi`（碰：等向听且 live 进张不降的有界放宽；吃：**pair-exact**，
    只评估平台实际会用的那一对 = 最后一个合法选项）。

为什么这两条**可叠加**：R1029 判定差距在"听牌速度"，且出牌轴已被证明不是漏点
（非最小向听率 0.00%），剩余自由度正是 (a) 并列路线选择、(b) 副露接受率；
两者分别落在**弃牌**与**窗口**两条互不重叠的决策路径上。

证据 / 门禁：
  * 出牌轴：自对弈台（已用 c151 vs tugc 双重标定）`c151 - speedvalue` 胜局轴 t=-2.90；
  * 副露轴：真机足迹 +17 决策/房，对齐测得的 14.9/房 副露缺口（R1036）；
  * 台子对副露轴**不可信**（+26% 副露偏差）⇒ 本臂必须在真机判。
"""
from __future__ import annotations

from .speedchirealized import SpeedMeldMore0Chi
from .speedvalue import SpeedValue


class SpeedValueMeldMore0Chi(SpeedValue, SpeedMeldMore0Chi):
    def __init__(self, name="speedvaluemeldmore0chi"):
        super().__init__(name)
