# -*- coding: utf-8 -*-
"""SpeedC168 —— **时间预算版有界真进张**：c159 路线在 M=10 下的安全退路。

正常情况下对轻量排序前 K 个候选调用 real_ukeire；一旦本决策的墙钟预算
耗尽，剩余候选退回轻量 `neigh_tiles + visible_counts` 评分。墙钟在并发
GIL 竞争下会反映真实线程等待，因此能自动避免多秒尾延迟。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedc135 import _pref
from .speedc151 import ROUTE_BONUS, _pair_count
from .speedc159 import W_CONSERVATIVE, phase_weight
from .ukeire import neigh_tiles, real_ukeire, visible_counts
from .speedc167 import _fast_live


def _pick_discard_timed(hand, drawn, exposed, gangs, god_meld=True, view=None,
                        river_len=0, weights=W_CONSERVATIVE, topk=4, budget_ms=30.0):
    t0 = time.perf_counter()
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
        cheap.append((d, rem, s, wcnt, route, _fast_live(rem, vis)))
    if not cheap:
        return hand[0]
    ranked = sorted(cheap, key=lambda x: (0 if x[2] == 0 else 1,
                                          -(x[3] if x[2] == 0 else 0),
                                          -(x[5] + x[4]),
                                          _pref(x[0], hand),
                                          -1 if x[0] == drawn else 0))
    keep = [x[0] for x in ranked[:max(1, int(topk))] if x[2] > 0]
    exact_u = {}
    # 为避免在并发高峰继续叠加昂贵调用，严格按墙钟预算逐个尝试。
    for d in keep:
        if (time.perf_counter() - t0) * 1000.0 >= budget_ms:
            break
        row = next(x for x in cheap if x[0] == d)
        try:
            uu = real_ukeire(row[1], exposed=exposed, gangs=gangs, visible=vis,
                             god_meld=god_meld)
            exact_u[d] = float(uu[0] or 0)
        except Exception:
            exact_u[d] = None
    best_key, best_tile = None, None
    for d, rem, s, wcnt, route, cheap_u in cheap:
        if s > 0 and d in exact_u and exact_u[d] is not None:
            u = exact_u[d] + route
        elif s > 0:
            u = cheap_u + route
        else:
            u = 0.0
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC168(SpeedTUGC):
    WEIGHTS = W_CONSERVATIVE
    TOPK = 4
    BUDGET_MS = 30.0

    def __init__(self, name="speedc168", weights=None, topk=None, budget_ms=None):
        super().__init__(name)
        self.weights = tuple(weights) if weights is not None else tuple(self.WEIGHTS)
        self.topk = int(topk if topk is not None else self.TOPK)
        self.budget_ms = float(budget_ms if budget_ms is not None else self.BUDGET_MS)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        rl = 0
        try:
            rl = int((view or {}).get("river_len") or len((view or {}).get("river") or []))
        except Exception:
            rl = 0
        return _pick_discard_timed(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD,
                                   view=view, river_len=rl, weights=self.weights,
                                   topk=self.topk, budget_ms=self.budget_ms)
