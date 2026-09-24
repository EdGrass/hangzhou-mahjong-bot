# -*- coding: utf-8 -*-
"""SpeedValueBCVMeld —— **三层堆叠的部署臂**：BC 出牌排序 + 爆头可达性 V + 学习副露（对齐剂量 0.45）。

## 定位：这是**部署候选**，不做判词

- 三个层各自都已在役次里**单独验证**（BC：役 3；V：役 3；副露剂量：役 4/5）；
- 本臂 = 三者同时开（相对 `speedvalue` 是**三条变量**）⇒ **不能用它做"单变量判词"**，
  它只用于"若三条都被判正，正式赛就上这个最强配置"（以及 `var/_pick_arm.py` 的同台比较）；
- 组合的**相互作用未知但可解释**：出牌层（BC+V）与窗口层（副露）互不重叠（已分别测过足迹）。

## 契约

- MRO：`SpeedValueBCVMeld → SpeedValueBCV → SpeedValueBC → SpeedValueMeld → SpeedValue → SpeedC151…`
  ⇒ `_pick_discard` 取 **BC 版**、`value_of` 取 **BCV 版（含 V 项）**、`_want_claim` 取**副露网版**；
- 三个组件各自缺失 ⇒ 对应层退化（BC 网缺失 ⇒ 弃牌退回基线 V；副露网缺失 ⇒ 只退化窗口层）；
- **`self.stats` 必须初始化**（R1228：缺它会让 `_bc_pick` 抛异常并被兜底成别的策略 = 静默变形）。
"""
from __future__ import annotations

import collections
import os

from .c121meld import window_features                     # noqa: F401  （保持与其它副露臂同源）
from .speedc067 import _Net as _BCNet
from .speedc121 import _MeldNet
from .speedvalue import SpeedValue
from .speedvaluebc import DEFAULT_MODEL as DEFAULT_BC
from .speedvaluebcv import SpeedValueBCV
from .speedvaluemeld import DEFAULT_MELD, SpeedValueMeld


class SpeedValueBCVMeld(SpeedValueBCV, SpeedValueMeld):
    """BC + V + 学习副露（`claim_p=0.45`）——**部署用**，不做单变量判词。"""

    def __init__(self, name="speedvaluebcvmeld", model_path=None, margin=0.0,
                 max_candidates=4, shanten_lo=0, shanten_hi=2,
                 claim_p=0.45, meld_path=None):
        SpeedValue.__init__(self, name=name)              # 只初始化一次基类
        # --- 出牌层：BC 网（与 SpeedValueBC 同参）---
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        self.shanten_range = (int(shanten_lo), int(shanten_hi))
        self.stats = collections.Counter()                # ★ R1228：缺它会静默变形
        try:
            self.model = _BCNet(model_path or DEFAULT_BC)
            self.model_path = model_path or DEFAULT_BC
        except Exception:
            self.model = None
            self.model_path = None
        # --- 出牌层：V 项（class 属性 W_TILES=5.0 已由 SpeedValueBaotouV5 提供）---
        # --- 窗口层：副露网（与 SpeedValueMeld 同参）---
        self.claim_p = float(claim_p)
        try:
            self._mnet = _MeldNet(meld_path or DEFAULT_MELD)
        except Exception:
            self._mnet = None
