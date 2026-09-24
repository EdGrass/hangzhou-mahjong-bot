# -*- coding: utf-8 -*-
"""SpeedC203 —— **带宽规则**版"待ち形状优先"：只在 u1 离最大值 ≤ DELTA 的候选里比形状。

为什么（R545）：加权项 λ 加到 8 也只改 4.5% 的决策 ⇒ u1 的量级差太大，加权没用。
正确做法是**带宽**：先把"进张数略少但形状更好"的候选纳进来，再按両面数排序。
DELTA 由环境变量 C203_DELTA 控制（单位：真进张张数）。
"""
from __future__ import annotations
import collections, os
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts


def _ryanmen(h13):
    c = collections.Counter(h13)
    n = 0
    for suit in "wbt":
        for i in range(2, 8):
            if (str(i) + suit) in c and (str(i + 1) + suit) in c:
                n += 1
    return n


class SpeedC203(SpeedTUGC):
    DELTA = float(os.environ.get("C203_DELTA", "4"))

    def __init__(self, name="speedc203"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        vis = None
        if view:
            try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            except Exception: vis = None
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try: s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0), exposed_melds=exposed, gangs=gangs)
            except Exception: continue
            cands.append((d, rem, s))
        if not cands: return hand[0]
        smin = min(c[2] for c in cands)
        grp = [c for c in cands if c[2] == smin]
        scored = []
        for d, rem, s in grp:
            if s == 0:
                try: u = float(len(waits(rem, exposed_melds=exposed, gangs=gangs)))
                except Exception: u = 0.0
            else:
                try: u = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
                except Exception: u = 0.0
            scored.append((d, u, _ryanmen(rem), s))
        umax = max(x[1] for x in scored)
        band = [x for x in scored if x[1] >= umax - self.DELTA]
        # 形状优先，再进张，再 _pref
        best = min(band, key=lambda x: (-x[2], -x[1], _pref(x[0], hand), -1 if x[0] == drawn else 0))
        return best[0]
