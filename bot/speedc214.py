# -*- coding: utf-8 -*-
"""SpeedC214 —— c211 的**单变量**候选：翻转"摸切偏好"（`_pick_discard` 排序键最后一位）。

c135 以来的排序键末位是 `-1 if d == drawn else 0` ⇒ **同分时优先摸切**。
而实测（R572）：top32 的摸切率比我们低 6~8pp（k=8 时 56% vs 62%）
—— 他们更常"把摸到的牌留下、打掉手里的旧牌"。
本候选把末位反转为 `0 if d == drawn else -1`（同分时优先**手切**），其余逐位不变。

注意：末位只在 `(向听, 听牌张数/进张, _pref)` 全部相同时才起作用 ⇒ footprint 可能极小，
先用分歧率验证（R545 纪律：<10% 视为"没跑到"）。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc211 import SpeedC211
from .speedc152 import W_GRADED, _pair_count
from .speedc135 import _pref
from .ukeire import real_ukeire, visible_counts


def _pick_discard_teashi(hand, drawn, exposed, gangs, god_meld=True, view=None):
    cands = []
    for d in sorted(set(hand)):
        rem = list(hand); rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs, god_meld=god_meld)
        except ValueError:
            continue
        cands.append((d, rem, s))
    if not cands: return hand[0]
    smin = min(c[2] for c in cands)
    vis = None
    if view:
        try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        except Exception: vis = None
    best_key, best_tile = None, None
    for d, rem, s in cands:
        if s != smin: continue
        wcnt = 0.0; u = 0.0
        if s == 0:
            try:
                ws = waits(rem, exposed_melds=exposed, gangs=gangs); v = vis or {}
                wcnt = float(sum(max(0, 4 - int(v.get(t, 0))) for t in ws))
            except Exception: wcnt = 0.0
        else:
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis, god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception: u = 0.0
            u += float(W_GRADED.get(_pair_count(rem), 0.0))
        # ★ 唯一差别：末位反转（同分时优先「手切」而不是「摸切」）
        key = (s, -wcnt, -u, _pref(d, hand), 0 if d == drawn else -1)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC214(SpeedC211):
    def __init__(self, name="speedc214"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_teashi(hand, drawn, exposed, gangs,
                                    god_meld=self.GOD_MELD, view=view)
