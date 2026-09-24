# -*- coding: utf-8 -*-
"""SpeedC156 —— **在跑候选 c151 + 学习到的选择性副露**（单变量：只动副露门控）。

依据（本会话新证据 + 项目旧口径互相印证）：
- **同房同巡分层**（§9.66）：强者的听牌优势一大半来自**副露局的占比**——他们 74.5% 的局有副露（我们 61.0%），
  而"有副露"局的 8 巡听牌 56.7% vs 门清 39.4% ⇒ 副露是"快"的那一档；我方在"有副露"局里也不差（52.6%），
  差的是**把多少局推进这一档**；
- `bot/speedc121.py` 的旧口径（300 房重建手牌）：我方窗口索取率 **36.5%**、高胡率教师 **42.2%**，
  而"放宽门控"（speedtug/SpeedTU/speedtugh，索取率 57~60%）真机 **−25~−47/房** ⇒ 要的是**选择性多要一点**；
- **但 `speedc121` 从未上过真机**（`auto_ranking` 409 房里 0 房）⇒ 这条"学习到的选择性副露"是**未测**的；
- 且 c121 当时是配 **BC 弃牌层**测的；**配 c151（当前最优候选）没试过**。

本臂与 `speedc151` 的**唯一差别**：`_want_claim` 在质量门控（C136/C121 的严格基线）**说"不要"**的窗口上，
额外用学习到的副露网络（`var/c121_meld_net.pt`，141 维窗口特征）**补一部分"要"**（默认阈值 0.60）；
**绝不否决**基线的任何一次索取（单向增加，下行有界）。

预期（先写）：副露/局与"有副露局占比"↑（目标：占比 61% → 70%+）、8 巡听牌 ↑、胡率 ↑、番/胡 略 ↓；
判据仍是 `tools/ab_readout.py` 净胜/房（150 房/臂、t≥1.5）+ 机制层（`ab_mechanism`/`ab_tenpai`/`_own_fan_audit`）。
"""
from __future__ import annotations

import os

from .c121meld import window_features
from .speedc121 import _MeldNet
from .speedc151 import SpeedC151

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MELD = os.path.join(ROOT, "var", "c121_meld_net.pt")


class SpeedC156(SpeedC151):

    def __init__(self, name="speedc156", claim_p=0.60, meld_path=DEFAULT_MELD):
        super().__init__(name)
        self.claim_p = float(claim_p)
        self._mnet = _MeldNet(meld_path)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True                      # 基线已要 ⇒ 直接要（本臂**不否决**任何基线索取）
        try:
            offer = view.get("offer_tile")
            if not offer:
                return False
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            feat = window_features(hand, melds, list(view.get("river") or []),
                                   view.get("all_melds") or [], offer, kind)
            p = float(self._mnet.prob([feat])[0])
        except Exception:
            return False
        return p >= self.claim_p
