# -*- coding: utf-8 -*-
"""SpeedC177 —— fast c136：质量感知副露门控，用轻量可见进张代理替代逐候选 real_ukeire。

逻辑与 c136 相同：严格门控拒后，若副露后向听不变且轻量进张代理变多则接受。
只是把 `_state` 的 real_ukeire 换成 `_fast_live`（neigh_tiles + visible_counts）。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

from .speed import _chi_pairs
from .speedc164 import _fast_live
from .speedtugc import SpeedTUGC
from .ukeire import visible_counts


def _fast_state(hand, e, g, vis, god_meld=True):
    try:
        s = exact_shanten(hand, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g,
                          god_meld=god_meld)
    except Exception:
        return None
    if s == 0:
        return (s, None)
    return (s, float(_fast_live(hand, vis)))


def _after_best_fast(hand, offer, kind, pair, e, g, vis, god_meld=True):
    h2 = list(hand)
    try:
        if kind == "peng":
            for _ in range(2):
                h2.remove(offer)
            e2, g2 = e + 1, g
        elif kind == "gang_ming":
            for _ in range(3):
                h2.remove(offer)
            e2, g2 = e + 1, g + 1
        else:
            for x in pair:
                h2.remove(x)
            e2, g2 = e + 1, g
    except Exception:
        return None
    best = None
    for d in sorted(set(h2)):
        h3 = list(h2)
        h3.remove(d)
        if len(h3) != 13 - 3 * e2 - g2:
            continue
        st = _fast_state(h3, e2, g2, vis, god_meld)
        if st is None:
            continue
        k = (st[0], -(st[1] or 0))
        if best is None or k < best[0]:
            best = (k, st)
    return best[1] if best else None


class SpeedC177(SpeedTUGC):
    def __init__(self, name="speedc177"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        before = _fast_state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[1] is None:
            return False
        if kind == "chi":
            opts = [("chi", p) for p in _chi_pairs(hand, offer)]
        else:
            opts = [(kind, None)]
        for k, p in opts:
            after = _after_best_fast(hand, offer, k, p, e, g, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] == before[0] and after[1] > before[1]:
                return True
        return False
