# -*- coding: utf-8 -*-
"""SpeedC151B —— `speedc151` 的**有界延迟**孪生体（预算 40ms）。为下一役的组合臂准备。

为什么需要它（R783，2026-09-21 实测）：
  · `speedc151` 内部的 `real_ukeire` 是**无界**的，最坏单次决策可远超 2s 预算；
  · 本类把 `budget_ms=40.0` 交给 c151 **自带**的有界路径
    （`SpeedC151._pick_discard` 里 `deadline`/`fallback` 那一套）⇒ 语义 =
    "**预算内按 c151 走，超预算干净回退到基线 `_best_discard_t`**"，
    不做"把 None 当 0"那种有偏比较。
  · 实测（R783，599 个真实决策点）：**有界 vs 无界 c151 分歧 0/599**
    ⇒ 它在本池的真实局面上与 `speedc151` **逐决策等价**，只是把最坏延迟封顶。

⚠ **不要改 `speedc151` 本身**（本役仍在用它）；本文件只是同名类的独立子类。
⚠ 本文件**不在** `run_bot.STRATEGY_FACTORIES` 里 ⇒ 对在途战役**完全惰性**（显式注册表，无自动发现）。
"""
from __future__ import annotations

from .speedc151 import SpeedC151

NAME = "speedc151b"
BUDGET_MS = 40.0


class SpeedC151B(SpeedC151):
    """等价于 `SpeedC151(name="speedc151b", budget_ms=40.0)`。"""

    def __init__(self, name=NAME, budget_ms=BUDGET_MS):
        super().__init__(name=name, budget_ms=budget_ms)