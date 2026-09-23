# -*- coding: utf-8 -*-
"""SpeedC136 —— `speedtugc` 的**单变量**候选：副露门控改为**质量感知**。

基线（严格门控）：`after_shanten < before_shanten` 才吃/碰 —— 即**向听必须严格下降**。
本候选在同一判据上补一条：
    `after_shanten == before_shanten` **且** 吃/碰后的最优 13 张形式
    **真进张(real_ukeire) 变多** ⇒ 也接受。

为什么（2026-09-16 真机窗口实测，252 个可副露窗口）：
- 严格门控接受 **69.0%**；放宽到"向听不恶化即可"（`speedtug` 的做法）接受 **98.4%**；
- 两者之间那 **74 个"向听不变"的副露里，77%（57 个）真进张变好**，平均 **+14.89 张**（中位 +10）；
- 质量感知门控接受 **91.7%** ⇒ 副露率大约从 0.87 抬到 ~1.15，**正好落在全场 1.087–1.320 区间内**，
  但只收"确实把手牌变好"的那些（`speedtug` 是无差别收下，包含 23% 会把手牌变差的）。

与 `speedtug` 的区别：`speedtug` = `allow_equal`（不看质量）；本候选 = **只收质量变好的**。
与已作废的 c117/c132 无关（那两个动的是出牌，且用的是邻接代理）。

成本：每个窗口 ~1–4 个候选 × 最小向听组内的真进张（记忆化后单次 0.01–18ms）⇒ 必须量 1s 窗口延迟。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speed import _chi_pairs
from .ukeire import real_ukeire, visible_counts


def _state(hand, e, g, vis, god_meld=True):
    try:
        s = exact_shanten(hand, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g,
                          god_meld=god_meld)
    except Exception:
        return None
    if s == 0:
        return (s, None)                 # 已听牌：真进张定义不适用，交给严格判据
    u = real_ukeire(hand, exposed=e, gangs=g, visible=vis)
    return (s, float(u[0] or 0))


def _after_best(hand, offer, kind, pair, e, g, vis, god_meld=True):
    """吃/碰后，对每个合法弃牌取 (向听, 真进张) 最优的 13 张形式。"""
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
        st = _state(h3, e2, g2, vis, god_meld)
        if st is None:
            continue
        k = (st[0], -(st[1] or 0))
        if best is None or k < best[0]:
            best = (k, st)
    return best[1] if best else None


class SpeedC136(SpeedTUGC):
    def __init__(self, name="speedc136"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        # 严格判据不过 ⇒ 再看"向听不变但真进张变好"
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        before = _state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[1] is None:
            return False
        if kind == "chi":
            opts = [("chi", p) for p in _chi_pairs(hand, offer)]
        else:
            opts = [(kind, None)]
        for k, p in opts:
            after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] == before[0] and after[1] > before[1]:
                return True
        return False
