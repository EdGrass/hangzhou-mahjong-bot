# -*- coding: utf-8 -*-
"""SpeedC143 —— **低延迟版组合臂**：C136（质量副露）+ C141（财飘弃胡），**不含 C135**。

用途：若 C142（含 C135 真进张出牌）的热态延迟基准不达标（出牌路径 >3s），
用本臂顶上——出牌路径 100% 等于 `speedtugc`（p99≈66ms），只在**副露窗口**加了计算
（实测 p99 30ms / max 619ms，预算 1s）。

MRO：SpeedC143 → SpeedC136 → SpeedC141 → SpeedTUGC ⇒
`_want_claim` 取 C136、`_best_giveup` 取 C141、`_pick_discard` 与其他一律 `SpeedTUGC`。
"""
from __future__ import annotations

from .speedc136 import SpeedC136
from .speedc141 import SpeedC141


class SpeedC143(SpeedC136, SpeedC141):
    def __init__(self, name="speedc143"):
        super().__init__(name)
