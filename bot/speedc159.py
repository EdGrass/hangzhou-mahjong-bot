# -*- coding: utf-8 -*-
"""SpeedC159 —— **分时段的压对数**（c151 的单变量：把"多对子惩罚"的强度按巡目调度）。

新证据（2026-09-16 22:1x，`var/_pairbreak_by_turn.py`，本役 dec 口径 + §9.64 门户口径）：

| 拆对率 | T1 | T2 | T3 | T4 | T6 | T8 |
|---|---|---|---|---|---|---|
| 基线 speedtugc | 3.8% | 3.3% | 2.6% | 3.2% | — | — |
| **c151（在跑）** | **9.0%** | **10.7%** | 7.9% | 7.6% | — | — |
| **强者（同房同巡）** | **2.3%** | — | — | 6.5% | **10.1%** | **11.8%** |

⇒ c151 的"一刀切"惩罚**早期过猛**（T1 9.0% vs 强者 2.3%）、**中后盘不足**（T6/T8 低于强者）。
⇒ 本臂把它做成**按牌河长度调度的权重**（river_len ≈ 4×巡目）：
   `river_len < 12`（≈前 3 巡）权重 **0.0（=不压对数，退回 c150 行为）**；`12~28`（≈4~7 巡）**1.0**；`> 28`（≈8 巡后）**1.5**。

其余 100% 继承 c151（含 C036 弃胡、副露质量门控、真进张并列），**只改并列项里那个加成的强度**。
注意：权重是**局部变量**（不用模块级可变全局）—— 本 bot 一进程跑 10 场并发，改全局会串场。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc150 import SpeedC150
from .speedc135 import _pref
from .speedc151 import ROUTE_BONUS, SpeedC151, _pair_count
from .ukeire import real_ukeire, visible_counts


# 三档权重：(前 3 巡, 4~7 巡, 8 巡后)。c159 用保守档；c159b 用加力档（见 STATUS §9.74）。
W_CONSERVATIVE = (0.0, 1.0, 1.5)
W_FORCE = (0.0, 1.5, 2.5)


def phase_weight(river_len, weights=W_CONSERVATIVE):
    """按"本局公开弃牌总数"给压对数项定权重（river_len ≈ 4 × 巡目）。"""
    try:
        rl = int(river_len or 0)
    except Exception:
        rl = 0
    if rl < 12:
        return float(weights[0])
    if rl <= 28:
        return float(weights[1])
    return float(weights[2])


def _pick_discard_phase(hand, drawn, exposed, gangs, god_meld=True, view=None, river_len=0,
                        weights=W_CONSERVATIVE):
    """c151 的并列键 + **分时段**的多对子加成（唯一差别）。"""
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
    vis = None
    if view:
        try:
            vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        except Exception:
            vis = None
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
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis, god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception:
                u = 0.0
            if _pair_count(rem) <= 2:
                u += ROUTE_BONUS * w
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC159(SpeedC151):

    WEIGHTS = W_CONSERVATIVE

    def __init__(self, name="speedc159", weights=None):
        super().__init__(name)
        self.weights = tuple(weights) if weights is not None else tuple(self.WEIGHTS)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        rl = 0
        try:
            rl = int((view or {}).get("river_len") or len((view or {}).get("river") or []))
        except Exception:
            rl = 0
        return _pick_discard_phase(hand, drawn, exposed, gangs,
                                   god_meld=self.GOD_MELD, view=view, river_len=rl,
                                   weights=self.weights)
