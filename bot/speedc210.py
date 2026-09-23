# -*- coding: utf-8 -*-
"""SpeedC210 —— c152（全机制束）的**单变量**候选：已听牌段并列键改用「**活张数**」。

与 c152 唯一的差别：`s==0` 时原用 `wcnt = len(waits(rem))`（**听几种牌**），
本候选换成 `sum(max(0, 4 - vis[t]) for t in waits(rem))`（**还剩几张**，扣自家手牌+弃牌河+四家副露）。
`s>0` 分支（含 c151/c152 的分档路线加成）逐位不变。

离线证据（2026-09-19）：
- 对 c135 的分歧率：**听牌点 12.4%**（1032 个听牌点里 128 个改选）⇒ 过了 R545 的 10% footprint 门槛；
- 配对 rollout（`var/_rollout_win.py`，1472 零副露局）：和了率 18.07% → **18.34%（+0.27pp）**，
  McNemar 22:26（SE≈0.47pp）⇒ 点估计为正、与原理同向，但样本不足以单独判定。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc152 import SpeedC152, W_GRADED
from .speedc152 import _pair_count
from .speedc135 import _pref
from .ukeire import real_ukeire, visible_counts


def _pick_discard_live(hand, drawn, exposed, gangs, god_meld=True, view=None):
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
            # ★ 唯一差别：活张数（原 c152 用 len(waits) 的种类数）
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
            u += float(W_GRADED.get(_pair_count(rem), 0.0))
        key = (s, -wlive, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC210(SpeedC152):
    def __init__(self, name="speedc210"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_live(hand, drawn, exposed, gangs,
                                  god_meld=self.GOD_MELD, view=view)
