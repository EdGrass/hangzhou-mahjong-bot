# -*- coding: utf-8 -*-
"""SpeedValuePairLin —— **线性对子保持剂量**（`SpeedValue` + 每个"第 3 个以上"的对子给分）。

## 为什么需要"线性"版本

对子 = 碰的资源；而我们的缺口链已经量到座位级（§V.36）：

| 证据 | 数值 |
|---|---|
| 同房 TOP32 对账（本役 88 房） | 副露/轮 **0.396 vs 我们 0.298（−25%）**、爆头/胡 **28.7% vs 22.5%**、杠开/胡 **1.83% vs 1.16%**、番/胡 **1.42 vs 1.31** |
| `var/_midgame_strat.py`（既有） | k=8 时我们**门清 47.9% vs top32 34.2%**；2+ 副露 **15.6% vs 27.8%** |
| R949 | 第 7 巡后手里 **≥3 对：我们 7.5% vs 头部 25.2%（3.4×）** |
| R1011/R1013 | `P(爆头 | 副露数) = 19.7%(0) → 28.6%(1) → 46.1%(2) → 71.4%(3)`（爆头 ×2 番） |
| R1186 足迹 | 现成的**阶梯**剂量 `speedvaluepairr2/r4/r8`（"剩 ≥3 对"给固定分）只动 **2.9~3.5%** 决策 ⇒ 过窄 |
| 今日实测 | `speedvalue` → `speedvaluepairr8`（+0.64 分，阶梯）：**746/21,394 = 3.5%**，action 差异 0 |

⇒ 阶梯版只在"跨过 3 对这道线"时发力，作用面必然窄。**线性版**改成
`+k × max(0, 对数 − 2)`：只要**对子数不同**（含 3 对 vs 4 对）就会改变排序 ⇒ 作用面天然更宽。

## 契约（相对 `speedvalue` 只多一条变量）

- 只覆盖 `value_of`：在 `SpeedValue.value_of(...)` 之上加 `PAIR_PER_PAIR * max(0, pairs − 2)`；
- `_pick_discard` / 胡 / 杠 / 抓打圈 / 索取门控 **全部沿用 `SpeedValue`**（一字不改）；
- 白板不计入对子（与既有 `_PairReward` 口径一致）；
- `value_of` 返回 `None`（无法评估）时**不加分**，保持"没有信息就不出手"的保守语义。
"""
from __future__ import annotations

import collections as _c

from .speedvalue import SpeedValue


class _PairLin(SpeedValue):
    PAIR_PER_PAIR = 0.0        # 每个"第 3 个以上"的对子给的 V 分值

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None or not self.PAIR_PER_PAIR:
            return v
        try:
            pc = sum(1 for n in _c.Counter(x for x in rem if x != "白").values() if n >= 2)
        except Exception:
            return v
        if pc >= 3:
            v += self.PAIR_PER_PAIR * (pc - 2)
        return v


class SpeedValuePairLin16(_PairLin):
    """弱档：每多一对 +0.16 V 分（≈2 张活牌的权重）。"""
    PAIR_PER_PAIR = 0.16

    def __init__(self, name="speedvaluepairlin16"):
        super().__init__(name)


class SpeedValuePairLin32(_PairLin):
    """中档：每多一对 +0.32 V 分（≈4 张活牌）。"""
    PAIR_PER_PAIR = 0.32

    def __init__(self, name="speedvaluepairlin32"):
        super().__init__(name)


class SpeedValuePairLin64(_PairLin):
    """强档：每多一对 +0.64 V 分（= 既有最强阶梯档的单次量级）。"""
    PAIR_PER_PAIR = 0.64

    def __init__(self, name="speedvaluepairlin64"):
        super().__init__(name)
