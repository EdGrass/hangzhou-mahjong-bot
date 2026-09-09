# -*- coding: utf-8 -*-
"""SpeedM —— SpeedE + 副露放宽一档（C010，自动房对手指纹驱动，2026-09-09）。

动机（真异构指纹，自动房 10 场）：同桌席均副露 3.2/场（吃1.1 碰1.8 杠0.3）
vs SpeedE 0.3/场（~10×）——顶级 bot 明显更常副露；E 的窗口判据
（_want_claim：副露后向听【严格下降 after<before】才接受）可能过严。

SpeedM 与 SpeedE 的唯一差异 = 窗口响应判据放宽一档：
  可碰/吃/直杠 当且仅当：副露后向听【不恶化】（after <= before）且未听
  （before>0，已听保留听形不副露——与 E 相同）。
比 K2（按有效牌/进张判据，曾与 K1 捆绑测出负结果且受座对污染）更保守：
只放开"向听不变"这一档，不引入 ukeire 代理；单变量可测。
其余 100% 继承 SpeedE（出牌/胡/抓打圈/孤字 tie）。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

from .model import window_pending
from .speed import _chi_pairs, _claim_value, _melds_info
from .speede import SpeedE


def want_claim_mild(view, kind, allow_equal=True):
    """副露判据（可测纯函数）：after <= before（向听不恶化）且未听才副露。
    allow_equal=False 时退化为 E 的严格判据（after < before）。"""
    offer = view.get("offer_tile")
    if not offer:
        return False
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    if len(hand) != 13 - 3 * exposed - gangs:
        return False
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return False
    if before == 0:
        return False            # 已听：保留听形（与 E 相同）
    if kind == "chi":
        best = 99
        for pair in _chi_pairs(hand, offer):
            v = _claim_value(hand, offer, "chi", exposed, gangs, pair)
            if v < best:
                best = v
    else:
        best = _claim_value(hand, offer, kind, exposed, gangs)
    if allow_equal:
        return best <= before
    return best < before


class SpeedM(SpeedE):
    """E + 窗口放宽：向听不恶化（after<=before）即接受碰/吃/直杠。"""

    def __init__(self, name="speedM", allow_equal=True):
        super().__init__(name)
        self.allow_equal = bool(allow_equal)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            cnt = view["my_hand"].count(view["offer_tile"])
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_mild(view, "gang_ming",
                                                self.allow_equal):
                    return {"action": "gang", "tile": view["offer_tile"]}
                if cnt >= 2 and want_claim_mild(view, "peng",
                                                self.allow_equal):
                    return {"action": "peng", "tile": view["offer_tile"]}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi" and \
                    want_claim_mild(view, "chi", self.allow_equal):
                return {"action": "chi", "tile": view["offer_tile"]}
            return {"action": "pass", "tile": ""}
        return super().decide(view)
