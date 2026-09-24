# -*- coding: utf-8 -*-
"""SpeedC134 —— `speedtugc` 的**单变量**候选：开启**自己摸牌回合的暗杠/补杠**。

唯一差异：`SpeedTUGC.SELF_GANG` 由 `False` 改为 `True`（见 `bot/speedtugc.py:_maybe_gang`）。

为什么（2026-09-16 真机全量实测）：
- 我方 **257,284** 个摸牌决策里，可杠机会 **2,897** 个，实际杠 **21** 个（**0.7%**）；
  `speedtugc` 是 **0 / 1,373** —— 本族**完全没有自杠路径**：唯一的 gang 在 `response_peng`，
  且被 `want_claim_strict_meld`（「向听必须严格下降」）挡住，而**杠不改变面子数 ⇒ 永不满足**。
- 全场 `杠/轮` = **0.0375–0.0887**，我方 **0.0102** ⇒ 我们是该轴的**极端值**（4–9× 差距）。
- 机械依据：同种 4 张时第 4 张**无法参与任何面子/对子**（3 张已成刻子）⇒
  杠 = 把死牌换成**一次补牌**（+1 摸牌），补杠同理。
- 唯一真实代价：关闭**七对/豪华七对**路线 ⇒ `_maybe_gang` 按「路线」判断
  （已有副露直接杠；门清时只有「已听牌」或「七对向听明显更差」才杠）。
"""
from __future__ import annotations

from .speedtugc import SpeedTUGC


class SpeedC134(SpeedTUGC):
    SELF_GANG = True

    def __init__(self, name="speedc134"):
        super().__init__(name)
