# -*- coding: utf-8 -*-
"""SpeedC158 —— **副露侧大束**：c151（质量门控）+ 学习到的选择性补加（c156）+ **末盘放宽**。

两处增量（都是"单向增加、绝不否决基线"，所以下行有界）：
1. **学习补加（c156）**：在门控拒的窗口上用 `var/c121_meld_net.pt` 补教师式的索取（阈值 0.60）。
   预测效果：有副露局占比 61.2% → 66.6%（+5.4pp）※ `var/_c156_meldmix_pred.py`
2. **末盘放宽**：河牌长度 ≥ 40 且"副露后同向听、等张退化 ≤ 8 张"时也吃碰。
   依据：§9.69-补 —— 强者实际副露里我方门控会拒的 14.7%，画像正是"巡目 7 前后、等张退化 ~8 张、63% 含白"。
   预测效果：+1.4pp ※ `var/_late_meld_footprint.py`

合计预测：**+6.8pp**（61.2% → ~68%），目标（强者）74.5% ⇒ 补掉约一半的入口差；
机制闸门见 STATUS §9.68（有副露局占比须 +4pp 以上；番/胡 ≥ ~1.30、爆头占胡 ≥ ~25%）。
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc156 import SpeedC156
from .ukeire import visible_counts


class SpeedC158(SpeedC156):

    RIVER_LATE = 40        # 末盘判据：本局公开弃牌总数（不能用 view["turn"]——那是行动座位号）
    UKEIRE_TOL = 8         # 允许的等张退化（张）

    def __init__(self, name="speedc158"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        try:
            rl = int(view.get("river_len") or len(view.get("river") or []))
            if rl < self.RIVER_LATE:
                return False
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            e = len(melds)
            g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
            offer = view.get("offer_tile")
            if not offer or len(hand) != 13 - 3 * e - g:
                return False
            vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            before = _state(hand, e, g, vis, self.GOD_MELD)
            if before is None or before[1] is None:
                return False
            opts = ([('chi', p) for p in _chi_pairs(hand, offer)] if kind == "chi"
                    else [(kind, None)])
            for k, p2 in opts:
                after = _after_best(hand, offer, k, p2, e, g, vis, self.GOD_MELD)
                if after is None or after[1] is None:
                    continue
                if after[0] == before[0] and after[1] >= before[1] - self.UKEIRE_TOL:
                    return True
        except Exception:
            return False
        return False
