# -*- coding: utf-8 -*-
"""SpeedValuePlain —— `SpeedValue` 但**出牌器换回"纯进张"**（`SpeedTUGC._pick_discard` / `_best_discard_t`）。

## 为什么（R1215）

轴：**"番值换胡率"该不该换**。
- `bot/speedc217.py` 的自述给了真机读数：`speedc135`（"真进张弃牌"，即"用番值倾向选牌"）单独用是最差之一
  （**−0.418 分/席局**），而它的**进张命中率 99%**（过程侧最优）⇒ **怀疑"用番值换胡率"净效应为负**；
- 我们的 `SpeedValue` 正是"**用拟合 V（含 番 / 白板 / 活进张）取代纯 max-ukeire**"的弃牌器；
- 与 R1201 的审计合起来看：**单步最优命中率我们已追平 top32（94.7~95.4%）**，
  但 R1202 显示**同状态推进率仍差 5~7pp** ⇒ "换成什么"仍可能是净负（若它牺牲了推进）。

本臂就是这条假设的**最干净检验**：**除出牌器外一切与 `SpeedValue` 相同**。

## 契约（相对 `speedvalue` 只多一条）

- **只覆盖 `_pick_discard`**：胡 / 自杠 / 抓打圈 / 副露窗口 / 兜底路径 **100% 沿用 `SpeedValue`**；
- 出牌器直接调用 **`SpeedTUGC._pick_discard`**（= `_best_discard_t`，纯进张口径；该实现**不调用 `super()`**，
  因此 unbound 调用是安全的、不会改变 MRO 语义）；
- 异常 ⇒ 回落到 `SpeedValue._pick_discard`（零风险兜底）。

## 起役前足迹体检（R1186 纪律）

    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvalueplain --files 300 --phase draw --lowprio
"""
from __future__ import annotations

from .speedtugc import SpeedTUGC
from .speedvalue import SpeedValue


class SpeedValuePlain(SpeedValue):
    """`SpeedValue` + 出牌器换回纯进张（`_best_discard_t`）——单变量：只换选牌器。"""

    def __init__(self, name="speedvalueplain"):
        super().__init__(name=name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        try:
            return SpeedTUGC._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        except Exception:
            return super()._pick_discard(hand, drawn, exposed, gangs, view=view)
