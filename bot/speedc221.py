# -*- coding: utf-8 -*-
"""SpeedC221 —— **便宜的宽度修法**：只在 `s == 1`（差最后一步）用真进张打破并列。

动机（R764/R768/R770）：
  · 缺口集中在"卡在 1 向听"（未听牌局里 1 向听占 26% vs 顶级 22%）；
  · 基线 `_best_discard_t` 只在 `s == 0` 用宽度，`s >= 1` 全部落到静态 `_pref`；
  · `c135`/`c135d` 在**所有 s** 用真进张 ⇒ 合规 98~100%，但 p95 ~33~45ms、max ~150~190ms（R771/R773）。
本候选是它的**三分之一成本版**：
    s == 1  → 用 `real_ukeire` 的 live 打破并列（带 40ms deadline，超时干净回退）
    s != 1  → **原样调用基线 `_best_discard_t`**（含 s==0 的 waits 宽度，行为一字不改）
⇒ 与基线**唯一的差别**就是 1 向听那一格，**单变量、可解释、成本低**。
"""
from __future__ import annotations

import time

from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedt import _pref, _best_discard_t
from .ukeire import real_ukeire, visible_counts

BUDGET_MS = 40.0


def _best_discard_width_at_1sh(hand, drawn, exposed, gangs, god_meld=True, view=None,
                               budget_ms=BUDGET_MS):
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
    if smin != 1:                      # 只在 1 向听改；其余整格交给基线
        return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
    vis = None
    if view:
        try:
            vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        except Exception:
            vis = None
    deadline = time.monotonic() + budget_ms / 1000.0
    best, best_key = None, None
    for d, rem, s in cands:
        if s != smin:
            continue
        live = None
        try:
            live, _kinds = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                       god_meld=god_meld, deadline=deadline)
        except Exception:
            live = None
        if live is None:               # 超预算 ⇒ 整次决策干净回退基线（不做 None 当 0 的有偏比较）
            return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
        key = (-live, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best = key, d
    return best if best is not None else _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)


class SpeedC221(SpeedTUGC):
    def __init__(self, name="speedc221"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _best_discard_width_at_1sh(hand, drawn, exposed, gangs,
                                          god_meld=self.GOD_MELD, view=view)
