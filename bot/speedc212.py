# -*- coding: utf-8 -*-
"""SpeedC212 —— **双修正束**：c152 + ①已听牌段用活张数 ②去掉 C136（吃碰放宽）。

两个成分都是**离线轨迹级测过的**，且都是"纠正次优"（不引入新模型）：
  ① 活张数（c210）：听牌点分歧 13.4%；配对 rollout 和了率 +0.27pp（22:26，1472 局）
  ② 去 C136（c211）：副露/局 1.477 → 1.074；配对 rollout 和了率 **+0.57pp**（25:20，876 局）
     且与 09-19 另一次独立测量（tugc vs c136 = −0.54pp，3,364 局）方向与量级一致。
本类不含任何新参数；若真机读数无改善，可拆回 c210 / c211 分别归因。
"""
from __future__ import annotations

from .speedc152 import SpeedC152
from .speedc210 import _pick_discard_live
from .speedtugc import want_claim_strict_meld


class SpeedC212(SpeedC152):
    def __init__(self, name="speedc212"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_live(hand, drawn, exposed, gangs,
                                  god_meld=self.GOD_MELD, view=view)

    def _want_claim(self, view, kind, pair=None):
        if kind == "gang_ming" and self._want_ming_gang(view):
            return True
        return want_claim_strict_meld(view, kind, pair)
