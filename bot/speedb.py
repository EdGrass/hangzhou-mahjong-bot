"""SpeedB —— SpeedBase 增强变体（V1：副露收益判定）。

在 SpeedBase（可胡即胡 + 向听数弃牌）基础上，窗口不再无条件碰/杠：
仅在【副露后最优弃牌的精确向听 < 不副露的当前向听】时才碰/直杠/吃
（更快成型）；已听（before==0）不碰，保留听形与等待。

其余决策继承 SpeedBase。判据阈值后续由 Arena 对决数据调参（-1/0/+1 档）。
"""
from __future__ import annotations

import os

from mahjong.hu import is_win
from mahjong.shanten_exact import shanten as exact_shanten

from .model import window_pending
from .speed import SpeedBase, _best_discard, _melds_info
from .util import log

W = "白"


def _min_shanten_after_discard(hand, exposed, gangs):
    """弃 1 张后能达到的最小向听（hand 为副露后待出牌的手牌）。"""
    best = 99
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        if s < best:
            best = s
            if best == 0:
                break
    return best


def _claim_value(hand, offer, kind, exposed, gangs, chi_pair=None):
    """副露后（弃最优 1 张）的最小向听；无法副露返回 99。"""
    h = list(hand)
    if kind == "peng":
        if h.count(offer) < 2:
            return 99
        for _ in range(2):
            h.remove(offer)
        return _min_shanten_after_discard(h, exposed + 1, gangs)
    if kind == "gang_ming":
        if h.count(offer) < 3:
            return 99
        for _ in range(3):
            h.remove(offer)
        return _min_shanten_after_discard(h, exposed + 1, gangs + 1)
    if kind == "chi":
        if not chi_pair:
            return 99
        for t in chi_pair:
            if t not in h:
                return 99
            h.remove(t)
        return _min_shanten_after_discard(h, exposed + 1, gangs)
    return 99


def _chi_pairs(hand, offer):
    """吃牌可用组合（与引擎口径一致：同花差1/差2邻接）。"""
    if offer == W or offer[-1] not in "wbt":
        return []
    n = int(offer[0])
    suit = offer[1]
    hset = set(hand)
    out = []
    for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
        ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
        if 1 <= a <= 9 and 1 <= b <= 9 and ta in hset and tb in hset:
            out.append([ta, tb])
    return out


def _want_claim(view, kind):
    """收益判据：副露后成型是否严格更快（after < before）。"""
    offer = view.get("offer_tile")
    if not offer:
        return False
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    # 不副露基线：当前等待摸牌态的向听（摸牌前 concealed）
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        before = 99
    if before == 0:
        if os.environ.get("HM_TRACE"):
            log("claim-trace %s offer=%s cnt=%d before=0(已听) → 不副露", kind,
                offer, hand.count(offer))
        return False            # 已听：保留听形，不副露
    if kind == "chi":
        best = 99
        pairs = _chi_pairs(hand, offer)
        for pair in pairs:
            v = _claim_value(hand, offer, "chi", exposed, gangs, pair)
            if v < best:
                best = v
        if os.environ.get("HM_TRACE"):
            log("claim-trace chi offer=%s pairs=%d before=%d after=%d → %s",
                offer, len(pairs), before, best,
                "要" if best < before else "过")
        return best < before
    v = _claim_value(hand, offer, kind, exposed, gangs)
    if os.environ.get("HM_TRACE"):
        log("claim-trace %s offer=%s cnt=%d before=%d after=%d → %s", kind,
            offer, hand.count(offer), before, v,
            "要" if v < before else "过")
    return v < before


class SpeedB(SpeedBase):
    def __init__(self, name="speedB"):
        super().__init__(name)

    def decide(self, view):
        offer = view.get("offer_tile")
        if window_pending(view) and offer:
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                # 直杠优先于碰（同收益判据）
                if cnt >= 3 and _want_claim(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and _want_claim(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi" and \
                    _want_claim(view, "chi"):
                return {"action": "chi", "tile": offer}
            return {"action": "pass", "tile": ""}
        # 非窗口决策完全继承 SpeedBase
        return super().decide(view)
