# -*- coding: utf-8 -*-
"""C117 学生策略：**进张数(ukeire)优先**的弃牌基线 + C073 学生网。

动机（2026-09-15 完整复盘口径）：
  - 真机前列玩家「胡牌速度」8.0-8.3 弃牌/胡，我方 8.74（慢 5%）；
  - 我方摸切率 52.5% vs 场中位 44%（基线 _best_discard_t 的 tie 里
    `-1 if d == drawn` 明确偏好摸切，且非听牌段完全不看进张）；
  - 离线审计 6000 个真实决策：基线在「最小向听组」内平均落后最优进张
    4.99 张（≈1.25 种种牌），线上策略（含网）仍落后 4.78 张。

本策略只改「基线弃牌」= 组内按 live ukeire 优先（其次 _pref，再保留摸切偏好）；
其余（胡/抓打圈/副露窗口、学生网重排）沿用 C068/C073 家族。
"""
from __future__ import annotations

import os

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc068 import C068Policy
from .speedt import _pref
from . import speedc067 as _c067

_ORIG_BEST = _c067._best_discard_t

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c073_orig_w4_net.pt")


def _live_ukeire(rem):
    try:
        from .c069routes import ukeire_counts
        _n, live = ukeire_counts(rem)
        return float(live)
    except Exception:
        return 0.0


def _best_discard_u(hand, drawn, exposed, gangs, god_meld=True):
    try:
        return _best_discard_u_impl(hand, drawn, exposed, gangs, god_meld)
    except Exception:
        return _ORIG_BEST(hand, drawn, exposed, gangs, god_meld)


def _best_discard_u_impl(hand, drawn, exposed, gangs, god_meld=True):
    """弃牌：向听最小 → 进张最宽 → _pref → 保留摸切偏好（末位）。"""
    best_key, best_tile = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs,
                              god_meld=god_meld)
        except ValueError:
            continue
        live = _live_ukeire(rem) if s <= 3 else 0.0
        key = (s, -live, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else (hand[0] if hand else None)


class C117Policy(C068Policy):
    def __init__(self, name="speedc117", model_path=None, lo=0, hi=2,
                 cand_order="ukeire", **kw):
        super().__init__(name=name, model_path=model_path or DEFAULT_MODEL,
                         lo=lo, hi=hi, cand_order=cand_order, **kw)

    def decide(self, view):
        old = _c067._best_discard_t
        _c067._best_discard_t = _best_discard_u
        try:
            return super().decide(view)
        finally:
            _c067._best_discard_t = old
