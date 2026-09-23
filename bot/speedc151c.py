# -*- coding: utf-8 -*-
"""SpeedC151C —— `speedc151` + **巡门控的多对子惩罚**（单变量：只给路线加成加一个时间闸）。

依据（R807，2026-09-21 ★ 新证据，同房同巡弃牌内容，n≈5 万/格）：

    | 巡 | "从对子拆" 我方 | 强者 | 两比例 z |
    |---:|---:|---:|---:|
    | **1** | **4.6%** | **1.9%** | **+24.8** |
    | 2 | 2.8% | 2.3% | +4.4 |
    | 3 | 3.8% | 4.3% | −4.2 |
    | 4 | 4.8% | 6.6% | −12.9 |
    | 5 | 5.9% | 8.7% | −17.8 |
    | 6 | 7.0% | 10.3% | −18.3 |
    | 7 | 8.0% | 11.3% | −16.8 |
    | 8 | 8.6% | 11.9% | −14.6 |

  · **巡 1**：我们拆对 **4.6%**，强者 **1.9%**（**z=+24.8，最显著的一条**）⇒ **我们第 1 巡拆对太多**；
  · **巡 4~8**：我们拆对**明显不够**（z=−13~−18）⇒ c151"鼓励拆对"的**方向是对的，但早期不该生效**。

⇒ 本候选 = `speedc151` **唯一**差别：**`巡 < GATE_TURN` 时不用路线加成**（退回**有界 c135**）。

契约（可逐段验证）：
  · `巡 >= GATE_TURN` ⇒ 与 `SpeedC151` **逐字相同**（走 `super()`）；
  · `巡 <  GATE_TURN` ⇒ 与 `SpeedC135D`（有界 c135、**无路线加成**）**逐字相同**；
  · `巡 = river_len // 4`（**项目既有口径**，见 `bot/c089rank.py:19-23`；`game.py:302` 保证 `river_len` 在线可得）；
  · `river_len` 缺失 ⇒ **视为 `GATE_TURN`**（保守：信息不足就走 c151 原行为，不悄悄退化成另一个候选）。

⚠ 未注册进 `run_bot.STRATEGY_FACTORIES`。
"""
from __future__ import annotations

from .speedc135d import SpeedC135D
from .speedc151 import SpeedC151

NAME = "speedc151c"
BUDGET_MS = 40.0
GATE_TURN = 3


class SpeedC151C(SpeedC151):
    """`巡 >= GATE_TURN` 走 c151；`巡 < GATE_TURN` 走有界 c135（无路线加成）。"""

    GATE_TURN = GATE_TURN

    def __init__(self, name=NAME, budget_ms=BUDGET_MS, gate_turn=None):
        super().__init__(name=name, budget_ms=budget_ms)
        self._budget_ms = budget_ms
        if gate_turn is not None:
            self.GATE_TURN = int(gate_turn)

    @staticmethod
    def _turn_of(view):
        """`river_len // 4`（项目既有口径）；拿不到 ⇒ None。"""
        if not view:
            return None
        rl = view.get("river_len")
        if rl is None:
            r = view.get("river")
            rl = len(r) if r else None
        if rl is None:
            return None
        return max(1, int(rl) // 4)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        t = self._turn_of(view)
        if t is not None and t < self.GATE_TURN:
            return SpeedC135D._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        return super()._pick_discard(hand, drawn, exposed, gangs, view=view)