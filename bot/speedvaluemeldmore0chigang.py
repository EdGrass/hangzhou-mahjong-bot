# -*- coding: utf-8 -*-
"""`SpeedValueMeldMore0ChiGang` —— 役 4 组合臂（役 3 + 积极杠）。

MRO 设计（三轴各自独立，互不复制逻辑）：
  * 吃   ← `ChiRealizedMixin`：pair-exact（只评估平台会用的那一对）；
  * 碰   ← `_MeldMoreBase`：等向听且 live 进张不降的有界放宽；
  * 明杠 ← `SpeedGangTake`：牌墙守卫内一律吃（台子 p10 t=−2.48 vs c151）；
  * 出牌 ← `SpeedGangTakeFixed`：gangs>0 用杠感知选张（R1016 的 P0 修复），gangs==0 用 `SpeedValue`。

为什么可以叠：三条改动分别落在**吃窗口 / 碰窗口 / 杠窗口 + 出牌**四条路径上，
`tests/test_speedvaluemeldmore0chi.py` 已钉住"出牌轴与副露轴正交"，本臂再钉"杠轴"。
"""
from __future__ import annotations

from .speedchirealized import ChiRealizedMixin
from .speedgangtakefixed import SpeedGangTakeFixed
from .speedmeldmore import _MeldMoreBase


class SpeedValueMeldMore0ChiGang(ChiRealizedMixin, _MeldMoreBase, SpeedGangTakeFixed):
    TOL = 0.0

    def __init__(self, name="speedvaluemeldmore0chigang"):
        super().__init__(name)
