# -*- coding: utf-8 -*-
"""SpeedC211 —— c152 的**单变量减法**：去掉 C136（吃/碰的「质量感知」放宽），只留 C144 明杠。

依据（2026-09-19 自研仪表 `var/_rollout_meld.py`，3,364 配对局）：
  speedtugc vs speedc136 ⇒ 副露/局 1.026 → 1.499（+46%），和了率 **19.89% → 19.35%（−0.54pp）**。
即 C136 的"多收质量变好的副露"在轨迹级是**中性偏负**的，而 c152 把它一起带上了。
本候选保持其它一切不变：`_pick_discard` 仍走 c152（含 c135 + 分档路线加成），
`_best_giveup` 仍走 C141，`SELF_GANG` 仍开，**只有 chi/peng 的门控退回严格判据**。
"""
from __future__ import annotations

from .speedc152 import SpeedC152
from .speedtugc import want_claim_strict_meld


class SpeedC211(SpeedC152):
    def __init__(self, name="speedc211"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        # 明杠：保留 C144 的"按路线收死牌"（同房配对证实 杠/轮 我方显著偏低）
        if kind == "gang_ming" and self._want_ming_gang(view):
            return True
        # 吃/碰：退回严格门控 ⇒ 去掉 C136 的放宽
        return want_claim_strict_meld(view, kind, pair)
