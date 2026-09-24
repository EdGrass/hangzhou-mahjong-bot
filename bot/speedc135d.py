# -*- coding: utf-8 -*-
"""SpeedC135D —— c135 的**有界延迟**版本（为"c135 那役"准备；**未注册**，不进 `run_bot` 注册表）。

动机（R734 实测，2026-09-20）：c135 单体在 2,452 个真实决策上
  p50=12.2ms / p95=65.8ms / **p99=117.9ms / max=274.5ms**，**10.4% 的决策 >50ms**
⇒ M=10 并发下（R648 实测）p99=1.05s、**max=2.06s 超 2s 预算**。
本版给 `real_ukeire` 传一个**每次决策共享的 deadline**；**一旦超时，整次决策干净回退到基线
`_best_discard_t`**——不做"把 None 当 0"那种有偏比较（`bot/ukeire.py` 的 docstring 明确禁止）。
⇒ 语义 = "**预算内按 c135 走，超预算按基线走**"，延迟上界 ≈ budget × 候选数 + 常数。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedt import _pref, _best_discard_t
from .ukeire import real_ukeire, visible_counts

BUDGET_MS = 40.0


def _best_discard_realukeire_bounded(hand, drawn, exposed, gangs, god_meld=True, view=None,
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
    vis = None
    if view:
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            vis = None
    deadline = time.monotonic() + max(0.0, float(budget_ms)) / 1000.0
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
                wcnt = 0
        else:
            if time.monotonic() >= deadline:      # ★ 预算用完 ⇒ 整次回退基线（不做有偏比较）
                return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld, deadline=deadline)
            except Exception:
                return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
            if uu is None or uu[0] is None:
                return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
            u = float(uu[0])
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC135D(SpeedTUGC):
    """c135 的有界延迟版（未注册）。"""

    def __init__(self, name="speedc135d", budget_ms=BUDGET_MS):
        super().__init__(name)
        self._budget_ms = budget_ms

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _best_discard_realukeire_bounded(hand, drawn, exposed, gangs,
                                                god_meld=self.GOD_MELD, view=view,
                                                budget_ms=self._budget_ms)
