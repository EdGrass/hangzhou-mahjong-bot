# -*- coding: utf-8 -*-
"""SpeedC146 —— **全缺陷组合臂（最大束）**：C144 明杠 + C134 自杠 + C136 吃碰质量 + C141 财飘。

为什么要"最大束"（2026-09-16 功率算术，写进 STATUS §4c-6）：
真机房级 SD≈145（原始分/房）；两臂差的标准误 SE_diff = 145·√2/√n（n = 每臂房数）。
- n=100（2.2 天，2 臂）：SE_diff≈20.5 ⇒ 真实效应 +20 只能给 z≈1.0（几乎判不出来）；
- n=200（4.3 天）：SE_diff≈14.5 ⇒ 同一效应 z≈1.4；
- 而**把 k 个机制捆在一个臂里**，效应是**相加**（Δ 变大）而阈值只随 SE 走
  ⇒ 在固定房数预算下，**"少臂 × 大束 × 长战役"** 的判出力显著高于"多臂 × 小束 × 短战役"。
（同一个 4.4 天预算：1 个 4 机制臂 z≈1.7；拆成 2 个臂各 2 机制 z≈0.6。）

四个成分各自对应**同房配对证实**的缺陷：
  - 明杠/轮 −0.0136（t=−11.7）、杠开/胡 −0.0091（t=−6.4）
  - 暗杠+补杠/轮 −0.0234（t=−27.6）
  - 吃/轮 −0.0576（t=−7.5）
  - 财飘/胡 −0.0052（t=−6.1）
机制均已**真机核对**：明杠 603/603 必补牌；杠在当局进度 p90=0.96/max=1.00 仍可（晚盘不限杠）；
全场 103 次财飘胡（我方 0 次）。

MRO：SpeedC146 → C144 → C136 → C141 → SpeedTUGC（+ `SELF_GANG=True` 即 C134 的开关）。
  - `_want_claim`：C144（明杠按路线）→ 链到 C136（吃碰质量感知）
  - `_best_giveup`：C141（弃白=财飘时链 +1 再估番）
  - `_maybe_gang`：`SpeedTUGC`（受 `SELF_GANG=True` 打开 ⇒ 暗杠/补杠）
  - `_pick_discard` / `decide`：与 `speedtugc` 逐位相同
"""
from __future__ import annotations

from .speedc136 import SpeedC136
from .speedc141 import SpeedC141
from .speedc144 import SpeedC144


class SpeedC146(SpeedC144, SpeedC136, SpeedC141):
    SELF_GANG = True          # = C134 的开关（暗杠/补杠走 SpeedTUGC._maybe_gang 的路线判断）

    def __init__(self, name="speedc146"):
        super().__init__(name)
