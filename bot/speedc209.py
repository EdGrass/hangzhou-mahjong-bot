# -*- coding: utf-8 -*-
"""SpeedC209 —— c135 的**单变量**候选：已听牌段的并列键从「等张**种类数**」换成「**活张数**」。

c135 的排序键：`(s, -wcnt, -u, _pref, -1 if d==drawn else 0)`，
其中 `wcnt = len(waits(rem))` 只在 `s==0` 时算，**是"听几种牌"而不是"还剩几张"**。
本候选把 s==0 的那一项换成 `sum(max(0, 4-vis[t]) for t in waits(rem))`（真·活张数，
扣自家手牌 + 弃牌河 + 四家副露；与 `_arm_cond.py` 的"活等张"同一口径）。
`s>0` 分支逐位不变。

原理：种类数与张数在"只剩 4 张的边张 / 被碰光的字牌"上会分歧 —— 听 1 种 3 张
好过听 2 种各 1 张。这是免费改进（不引入新模型、不增加搜索宽度）。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts


def _best_discard_live_waits(hand, drawn, exposed, gangs, god_meld=True, view=None):
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
    vis = None
    if view:
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            vis = None
    best_key, best_tile = None, None
    for d, rem, s in cands:
        if s != smin:
            continue
        wlive = 0.0
        u = 0.0
        if s == 0:
            try:
                ws = waits(rem, exposed_melds=exposed, gangs=gangs)
                v = vis or {}
                wlive = float(sum(max(0, 4 - int(v.get(t, 0))) for t in ws))
            except Exception:
                wlive = 0.0
        else:
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception:
                u = 0.0
        key = (s, -wlive, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC209(SpeedTUGC):
    def __init__(self, name="speedc209"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _best_discard_live_waits(hand, drawn, exposed, gangs,
                                        god_meld=self.GOD_MELD, view=view)
