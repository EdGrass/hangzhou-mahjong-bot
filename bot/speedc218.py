# -*- coding: utf-8 -*-
"""SpeedC218 —— `c211` **去掉 c146 的三件套**（明杠 C144 / 自杠 C134 / 财飘 C141），
只保留 **c135 的弃牌路径 + 严格副露门控（去 C136）**。

动机（R632/R633）：把 c211 的成分拆开。
- **c217** = c211 − **c135**（保留 c146 三件套）；
- **c218** = c211 − **c146 三件套**（保留 c135）；
- 两者合起来就能把 c211 的四类成分（c135 / route bonus / 明杠+自杠+财飘 / 去 C136）**逐个定符号**。

实现（三处）：
  ① `_want_claim` → 只用严格门控（同时去掉 C144 的"明杠按路线"与 C136 的"质量感知放宽"）；
  ② `SELF_GANG = False`（去掉 C134 的暗杠/补杠）；
  ③ `_best_giveup` → 回退到 `SpeedTUG`（即去掉 C141 的"弃白=财飘链+1"）。
其余（`_pick_discard` 仍是 c152 的 **c135 真进张 + route bonus**）不变。
"""
from __future__ import annotations

from .speedc211 import SpeedC211
from .speedtug import SpeedTUG
from .speedtugc import want_claim_strict_meld


class SpeedC218(SpeedC211):
    SELF_GANG = False          # ② 去掉 C134（暗杠/补杠）

    def __init__(self, name="speedc218"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        # ① 严格门控：既去掉 C144 的明杠路线，也去掉 C136 的放宽
        return want_claim_strict_meld(view, kind, pair)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        # ③ 回到 SpeedTUG 的原始弃胡判据（去掉 C141 的财飘链记账）
        return SpeedTUG._best_giveup(self, hand, exposed, gangs, fan_now, chain)
