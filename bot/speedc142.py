# -*- coding: utf-8 -*-
"""SpeedC142 —— **组合臂**：speedtugc + {c136 质量副露, c135 真进张出牌, c141 财飘弃胡}。

为什么做组合臂（2026-09-16，一个月爬山计划）：
每个单变量候选项估计只有 +4~+15 原始分/房，而真机 A/B 的分辨率是 ~±20 分/房
（100 房/臂）⇒ 单变量战役大概率读出「无差异」，等于白花 2.2 天。
把**已被单独量化、机制互不重叠**的三个改动叠成一个臂，期望效应变成 +15~+30，
才可能在一个战役内被判定。若组合臂判正 ⇒ 整体采用；若判负/平 ⇒ 再拆成单变量定位。

实现：**多继承 MRO**（不是手工转发，原因见下），MRO 顺序
    SpeedC142 → SpeedC136 → SpeedC135 → SpeedC141 → SpeedTUGC
⇒ 三个钩子各取一家：
  - `_want_claim`  ← C136（副露门控质量感知：向听不变但真进张变好也收）
  - `_pick_discard`← C135（未听牌并列改按真进张）
  - `_best_giveup` ← C141（弃白=财飘时链 +1 再估番，补上现有判据的低估）
  - 其余（`decide` / `_maybe_gang` / 胡 / 抓打圈 / `GOD_MELD=True`）→ `SpeedTUGC` 逐位相同。
⚠ 手工写 `SpeedC136._want_claim(self, ...)` 这种转发会**打坏 C136 内部的 `super()`**
（`super(SpeedC136, self)` 要求 self 是 SpeedC136 的实例），因此必须用多继承。
"""
from __future__ import annotations

from .speedc135 import SpeedC135
from .speedc136 import SpeedC136
from .speedc141 import SpeedC141


class SpeedC142(SpeedC136, SpeedC135, SpeedC141):
    def __init__(self, name="speedc142"):
        super().__init__(name)
