# -*- coding: utf-8 -*-
"""SpeedC187 —— **有硬时限的精确 c151**（面向 M>10 的安全候选）。

背景：`c151` 的增益来自精确真进张，但正式赛一个 `run_bot` 进程内多线程共享
GIL；M>10 时精确计算会拖尾。现有快版兜底 `c136/c146` 又完全不使用真进张，
等于放弃这条已验证的弃牌质量链。

本候选 = `SpeedC151` 的**唯一差别**：给每次出牌决策一个本地 deadline。
预算内与 c151 逐位相同；到期则这一次决策立即退回 `_best_discard_t`
（即 c136/c146 使用的基线弃牌路径）。它不使用任何廉价代理，也不会
把算了一半的真进张当结果，因此是"精确或基线"的单调安全折中。

预算默认 100ms/决策，实际值必须由 M=10/M=20 并发压测决定；本候选在
过 M=20 门禁前不得进入正式赛。
"""
from __future__ import annotations

from .speedc151 import SpeedC151

BUDGET_MS = 100.0


class SpeedC187(SpeedC151):

    def __init__(self, name="speedc187", budget_ms=BUDGET_MS):
        super().__init__(name, budget_ms=budget_ms)
