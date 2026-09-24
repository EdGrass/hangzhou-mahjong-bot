# -*- coding: utf-8 -*-
"""SpeedValueBaotouVMeld —— **V 分支的组合臂**：`SpeedValue` + 爆头可达性 V + 学习副露（对齐剂量 0.45）。

## 为什么需要它（§V.49 分支地图的最后一块）

若**役 3 判词为"BC 不采用、V 采用"**，新基线就是 `speedvaluebaotouv5`
⇒ 役 4 必须在**新基线之上**做（re-basing 规则）。该分支里可叠加的是**副露**（窗口层，与出牌层正交）。
`SpeedValueMeld` 挂的是 `speedvalue`（不含 V）⇒ 直接对照是**复合臂**；本文件把它挂到 **V 基线**上：

    MRO：SpeedValueBaotouVMeld → SpeedValueBaotouV5 → SpeedValueMeld → SpeedValue → SpeedC151 …
    ⇒ `value_of` 取 **V 版**（爆头可达性加权），`_want_claim` 取 **副露网版**，其余 100% 沿用 SpeedValue。

## 契约（相对新基线 `speedvaluebaotouv5` 只多一层）

- **draw 层逐位等价 `speedvaluebaotouv5`**（V 的 `value_of` 一字未改）；
- **window 层等价 `SpeedValueMeld(claim_p=0.45)`**（副露门控一字未改）；
- 两个"层"都不依赖对方：副露网缺失 ⇒ 只有窗口层退化（不报错、不换策略）。

⚠ 与 §V.41 相同的风险：V 是"该局以爆头胡"的预测器 ⇒ 追爆头可能换掉和牌速度；
判词必须**同时**看 **听牌率/胡率** 与 **番/胡**。
"""
from __future__ import annotations

import os

from .speedc121 import _MeldNet
from .speedvalue import SpeedValue
from .speedvaluebaotouv import SpeedValueBaotouV5
from .speedvaluemeld import DEFAULT_MELD, SpeedValueMeld


class SpeedValueBaotouVMeld(SpeedValueBaotouV5, SpeedValueMeld):
    """V（出牌层）+ 学习副露（窗口层）；剂量 `claim_p=0.45`（与 §V.35 对齐剂量一致）。"""

    def __init__(self, name="speedvaluebaotouvmeld", claim_p=0.45, meld_path=None,
                 w_tiles=None):
        SpeedValue.__init__(self, name=name)      # 只初始化一次基类
        if w_tiles is not None:
            self.W_TILES = float(w_tiles)
        self.claim_p = float(claim_p)
        try:
            self._mnet = _MeldNet(meld_path or DEFAULT_MELD)
        except Exception:
            self._mnet = None                     # 副露网缺失 ⇒ 只有窗口层退化
