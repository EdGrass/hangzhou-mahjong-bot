# -*- coding: utf-8 -*-
"""SpeedC167 —— **有界真进张**：c159 的精确路线评分，但只对轻量筛出的前 K 个候选算 real_ukeire。

动机：c159 在正式赛 M=10 下的尾延迟 >3s；根因是对每个最小向听候选都调用
`real_ukeire`（内部 O(邻居张数 × 手牌张数) 次精确向听）。本候选先用
`neigh_tiles + visible_counts + 对数路线项` 做廉价排序，只对 top-K 候选调用
`real_ukeire`，在保持 c159 评分口径的同时把昂贵调用数从 ~5-8 降到 K。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedc135 import _pref
from .speedc151 import ROUTE_BONUS, _pair_count
from .speedc159 import W_CONSERVATIVE, phase_weight
from .ukeire import neigh_tiles, real_ukeire, visible_counts


def _fast_live(rem, vis):
    return sum(max(0, 4 - int(vis.get(t, 0))) for t in neigh_tiles(rem))


def _pick_discard_bounded(hand, drawn, exposed, gangs, god_meld=True, view=None,
                          river_len=0, weights=W_CONSERVATIVE, topk=2):
    w = phase_weight(river_len, weights)
    cands = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs, god_meld=god_meld)
        except ValueError:
            continue
        cands.append((d, rem, s))
    if not cands:
        return hand[0]
    smin = min(c[2] for c in cands)
    vis = visible_counts(hand, river=(view or {}).get("river"),
                         all_melds=(view or {}).get("all_melds"))
    # 先给所有并列候选算廉价分；只把最好的 K 个送进精确 real_ukeire。
    cheap = []
    for d, rem, s in cands:
        if s != smin:
            continue
        wcnt = 0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                pass
        route = ROUTE_BONUS * w if _pair_count(rem) <= 2 else 0.0
        cheap.append((d, rem, s, wcnt, route))
    if not cheap:
        return hand[0]
    # s==0 不调用 real_ukeire；非听牌候选按轻量 live+route 排序后取前 K。
    ranked = sorted(cheap, key=lambda x: (0 if x[2] == 0 else 1,
                                          -(x[3] if x[2] == 0 else 0),
                                          -(0 if x[2] == 0 else _fast_live(x[1], vis) + x[4]),
                                          _pref(x[0], hand),
                                          -1 if x[0] == drawn else 0))
    keep = set(x[0] for x in ranked[:max(1, int(topk))])
    # 听牌候选不参与 real_ukeire；但若同组有非听牌候选，保留前 K。
    if any(x[2] == 0 for x in cheap):
        keep.update(x[0] for x in cheap if x[2] == 0)
    best_key, best_tile = None, None
    for d, rem, s, wcnt, route in cheap:
        u = 0.0
        if s > 0 and d in keep:
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception:
                u = 0.0
            u += route
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC167(SpeedTUGC):
    WEIGHTS = W_CONSERVATIVE
    TOPK = 2

    def __init__(self, name="speedc167", weights=None, topk=None):
        super().__init__(name)
        self.weights = tuple(weights) if weights is not None else tuple(self.WEIGHTS)
        self.topk = int(topk if topk is not None else self.TOPK)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        rl = 0
        try:
            rl = int((view or {}).get("river_len") or len((view or {}).get("river") or []))
        except Exception:
            rl = 0
        return _pick_discard_bounded(hand, drawn, exposed, gangs,
                                     god_meld=self.GOD_MELD, view=view,
                                     river_len=rl, weights=self.weights, topk=self.topk)
