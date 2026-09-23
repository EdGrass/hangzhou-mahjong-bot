# -*- coding: utf-8 -*-
"""SpeedC188 —— **安全版 c186**：学习副露 + 无白/真实进张变差时硬否决。

背景（2026-09-17 19:1x 同窗实测）：
- c186（claim_p=0.50）的额外覆盖几乎都落在高价值窗口：
  Δ向听=0、真进张上涨桶接受 88.4% vs c151 34.9%；
- 但它在同一批里对「Δ=0、真进张下跌」也 3/3 全收。
- 前期窗口解剖表明，模型多收的典型是「含白 + 中盘偏晚 + 真进张口径负收益」，
  其中含白可能承载爆头/四白，**不能一律否决**。

因此本候选只加一条保守护栏：
  1. base（c151/c136 质量门控）已要 ⇒ 原样接受；
  2. c186 模型额外想收：
     - 手里有白 ⇒ 放行（保留爆头/四白路线）；
     - 手里无白且可计算的真实进张/向听相比副露前严格变差 ⇒ 否决；
     - 无法计算或至少有一个合法吃法不更差 ⇒ 放行。
其余 100% 继承 c186。
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc151 import SpeedC151
from .speedc186 import SpeedC186
from .ukeire import visible_counts


class SpeedC188(SpeedC186):

    def __init__(self, name="speedc188", claim_p=0.50):
        super().__init__(name, claim_p=claim_p)

    def _want_claim(self, view, kind, pair=None):
        # c186 先给出「模型额外多收」的结果；base 已收的情况直接放行。
        if not super()._want_claim(view, kind, pair):
            return False
        try:
            if SpeedC151._want_claim(self, view, kind, pair):
                return True
            hand = list(view.get("my_hand") or [])
            offer = view.get("offer_tile")
            if not offer:
                return False
            # 含白代表爆头/四白路线，真进张不专门描述这种形态 ⇒ 不否决。
            if "白" in hand:
                return True
            melds = view.get("melds") or []
            e = len(melds)
            g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
            if len(hand) != 13 - 3 * e - g:
                return True
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
            before = _state(hand, e, g, vis, self.GOD_MELD)
            if before is None or before[1] is None:
                return True
            opts = [("chi", p) for p in _chi_pairs(hand, offer)] if kind == "chi" else [(kind, None)]
            for k, p in opts:
                after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
                if after is None or after[1] is None:
                    continue
                if after[0] < before[0]:
                    return True
                if after[0] == before[0] and after[1] >= before[1]:
                    return True
            return False
        except Exception:
            # 护栏自身异常时不改变 c186 行为，避免把候选变成“模型缺失/异常时乱 veto”。
            return True
