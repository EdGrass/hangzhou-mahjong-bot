# -*- coding: utf-8 -*-
"""`speedmeldmore` —— c151 的**有界风险**副露放宽：允许"宽度不掉超过 TOL"的等向听副露。

背景（本轮实测）：
- **我们副露偏少，且每个类别都少**：吃/局 **0.558 vs 顶级 0.618**；总副露/席局 **1.081 vs 1.235**（R888）；
- 而**吃三手双方都不做**（3+ 占比 0%，本 R 实测）⇒ 硬上限 `chi_cnt<2` **不是**杠杆；
- 既有的"质量感知"放宽（`speedc136`，已并入 c151）只收 **等向听且真进张变好** 的副露；
  它的接受率 91.7%，而"无差别收下"（`allow_equal`）会收 98.4%，其中 **23% 会把手牌变差**（c136 自述）。
- ⇒ 两者之间**从没测过**：**允许"宽度小幅下降"的等向听副露**（有界的风险换节奏）。

本臂（相对 c151 的唯一差别）：
    `_want_claim` 先在父类不过时，补一条：
        `s_after == s_before` 且 `live_after >= live_before - TOL`（TOL=2 张）⇒ 接受。
  - `TOL = 0` ⇒ 只收"等向听且宽度**不降**"的副露（比父类多一档"宽度恰好相等"，**不是**保真档）；
  - `TOL = 2` ⇒ 允许"最多掉 2 张活张"的等向听副露（**有界**：绝不接受向听变差、也绝不接受宽度掉超过 2）。

方向护栏（可测）：
  ① **超集性**：父类接受的，本臂一定接受（先调 super）；
  ② **有界性**：本臂新接受的每一次副露，向听不变且 `live_after ≥ live_before − TOL`；
  ③ **非 no-op**：存在真实窗口被本臂接受而父类拒绝。

⚠ 实现：`_want_claim` 的父类链是 C144→C136→SpeedTUGC；本臂只补"等向听 + 有界宽度损失"这一档，
  其余（向听严格下降 / 已听换听 / 明杠）全部沿用。
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc151 import SpeedC151
from .ukeire import visible_counts


class _MeldMoreBase(SpeedC151):
    TOL = 0.0        # 0 = 只收"宽度不降"的等向听副露（与父类同档的上界）

    def __init__(self, name="speedmeldmore"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        if kind not in ("chi", "peng"):
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        before = _state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[0] == 0 or before[1] is None:
            return False          # 已听牌交给父类；算不动则保守拒绝
        if kind == "chi":
            opts = [("chi", p) for p in _chi_pairs(hand, offer)]
        else:
            opts = [("peng", None)]
        for k, p in opts:
            after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] != before[0]:
                continue          # 只补"等向听"这一档（向听必须不变）
            if (after[1] or 0.0) >= (before[1] or 0.0) - self.TOL:
                return True
        return False


class SpeedMeldMore0(_MeldMoreBase):
    """最严档：只收"等向听且宽度不降"的副露（TOL=0）。⚠ 它**不**等于 c151（多了"恰好相等"这一档）。"""
    TOL = 0.0

    def __init__(self, name="speedmeldmore0"):
        super().__init__(name)


class SpeedMeldMore2(_MeldMoreBase):
    """候选：允许等向听副露把活张宽度最多降 2 张（有界风险换节奏）。"""
    TOL = 2.0

    def __init__(self, name="speedmeldmore2"):
        super().__init__(name)
