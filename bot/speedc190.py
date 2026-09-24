# -*- coding: utf-8 -*-
"""SpeedC190 —— **speedtugc + 学习副露 + 无白坏窗口否决**。

强场证据：二测 160 轮中 c151 的成对压对数路线失败（胜率 22.5%、8巡听牌 15.4%），
但同房 top32 副露接受率 58.4% vs 我方 41.5% 仍是最大机制缺口。
阈值校准：254 个有资格真实窗口上，speedtugc 基线接受 49.2%；学习层 p>=0.75 时总接受 57.5%，最接近 top32 的 58.4%（p=0.50 会接近全收）。
本候选把学习副露层从失败的 c151 家族剥出来，只叠在真机证据最厚的 `speedtugc` 上：
  - base（严格向听下降）已收 ⇒ 放行；
  - 学习网络额外想收 ⇒ 视作候选；
  - 额外候选若**无白且真实进张严格变差** ⇒ 否决；含白/爆头路线放行。
其余 100% 继承 speedtugc。
"""
from __future__ import annotations

import os

from .c121meld import window_features
from .speed import _chi_pairs
from .speedc121 import _MeldNet
from .speedc136 import _after_best, _state
from .speedtugc import SpeedTUGC
from .ukeire import visible_counts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MELD = os.path.join(ROOT, "var", "c121_meld_net.pt")


class SpeedC190(SpeedTUGC):

    def __init__(self, name="speedc190", claim_p=0.75, meld_path=DEFAULT_MELD):
        super().__init__(name)
        self.claim_p = float(claim_p)
        self._mnet = _MeldNet(meld_path)

    def _model_wants(self, view, kind):
        offer = view.get("offer_tile")
        if not offer:
            return False
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        feat = window_features(hand, melds, list(view.get("river") or []),
                               view.get("all_melds") or [], offer, kind)
        p = float(self._mnet.prob([feat])[0])
        return p >= self.claim_p

    def _extra_is_safe(self, view, kind, pair=None):
        """只否决“无白 + 真实进张严格变差”的额外副露；无法评估时放行。"""
        hand = list(view.get("my_hand") or [])
        if "白" in hand:
            return True
        offer = view.get("offer_tile")
        if not offer:
            return False
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if len(hand) != 13 - 3 * e - g:
            return True
        vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
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

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        try:
            if not self._model_wants(view, kind):
                return False
            return self._extra_is_safe(view, kind, pair)
        except Exception:
            return False
