# -*- coding: utf-8 -*-
"""SpeedC164 —— **快版 c159 路线**：分时段压对数，用轻量可见进张代理替代逐候选真进张。

正式赛 M=10 是一个进程内多线程共享策略；c150/c151/c159 的 real_ukeire
会在 GIL 下放大尾延迟。本候选只把 c135 的 `real_ukeire` 换成
`neigh_tiles + visible_counts` 的 O(手牌) 代理，仍在向听/等张主键之后作并列项。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedc135 import _pref
from .speedc151 import ROUTE_BONUS, _pair_count
from .speedc159 import W_CONSERVATIVE, phase_weight
from .ukeire import neigh_tiles, visible_counts


def _fast_live(rem, vis):
    return sum(max(0, 4 - int(vis.get(t, 0))) for t in neigh_tiles(rem))


def _pick_discard_fast_phase(hand, drawn, exposed, gangs, god_meld=True, view=None,
                             river_len=0, weights=W_CONSERVATIVE):
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
    best_key, best_tile = None, None
    for d, rem, s in cands:
        if s != smin:
            continue
        wcnt = 0
        u = 0.0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                pass
        else:
            try:
                u = float(_fast_live(rem, vis))
            except Exception:
                u = 0.0
            if _pair_count(rem) <= 2:
                u += ROUTE_BONUS * w
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC164(SpeedTUGC):
    WEIGHTS = W_CONSERVATIVE

    def __init__(self, name="speedc164", weights=None):
        super().__init__(name)
        self.weights = tuple(weights) if weights is not None else tuple(self.WEIGHTS)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        rl = 0
        try:
            rl = int((view or {}).get("river_len") or len((view or {}).get("river") or []))
        except Exception:
            rl = 0
        return _pick_discard_fast_phase(hand, drawn, exposed, gangs,
                                        god_meld=self.GOD_MELD, view=view,
                                        river_len=rl, weights=self.weights)
