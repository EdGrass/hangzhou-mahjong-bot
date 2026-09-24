# -*- coding: utf-8 -*-
"""SpeedC151 —— **多对子惩罚出牌**（`speedc150` 的单变量候选）。

⚠ 2026-09-17 00:10 方向更正（依据 STATUS §4c-67）：初版是"**保对子**"，但实测显示
**"持对数"与听牌率强负相关**（第 8 巡：1 对 63~72%、2 对 39~51%、**3~4 对 13~30%**），
而强玩家几乎从不停在 ≥3 对。⇒ 正确方向是**惩罚多对子、鼓励拆对**，不是保对子。

背景（2026-09-16，STATUS §4c-62 / §4c-63）：
- 我们与同池强玩家（rank 11）的差距是**听牌速度**（第 8 巡 45.8% vs 55.3%，+9.5pp）→ 胜率 +2.29pp；
- 但**"按进张出牌"我们已经有了**（C135：最小向听组内按真进张打破并列）；
- 因此在"速度"方向上剩下的手工可做之事是**让进张的取值带上路线偏好**：
  纯 `real_ukeire` 把"成对/成刻/字牌"与"孤张搭子"当等价，但前者除了进张还带**番/碰碰胡/对子安全**的价值。

本候选 = `speedc150`（含 C135）**唯一**差别：在 C135 的并列键里插入一个**路线项**：

    key = (向听, −听牌张数[s==0], **−(real_ukeire + 路线加成)[s>0]**, _pref, 摸切)

其中 `路线加成(d) = ROUTE_BONUS × (弃掉 d 后手里还剩几张 d)`
  - 即：**弃牌后还留着的同牌越少，越优先弃**（等价于"尽量保对子/刻子"）；
  - 这正是强玩家与我们的**实测行为差异**（拆对率 6.12% vs 我们 4.39%）的反向修正方向（我们更保对子）；
  - 用它当**并列项**（不是主键）⇒ 只在"向听相同 + 进张几乎相同"时才改变选择 ⇒ **下行有界**。

参数 `ROUTE_BONUS = 8.0`：含义是"把对数压回 ≤2 这一选择 ≈ 8 张进张的价值"（先取一个较大的值，若读数显示过度拆对再降）。
  - 若最终读数无变化，可先试 2 或 8（这是**单一旋钮 + 有明确语义**，便于定位）；
  - 这与"调阈值"不同：它改的是**评估里的一项**，语义是"保对的边际价值"。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc150 import SpeedC150
from .speedc135 import _pref
from .speedt import _best_discard_t
from .ukeire import real_ukeire, visible_counts


ROUTE_BONUS = 8.0


def _pair_count(hand):
    """手牌里的对数（≥2 张的牌型数）。"""
    try:
        import collections as _c
        return sum(1 for v in _c.Counter(hand).values() if v >= 2)
    except Exception:
        return 0


def _route_bonus(rem_after_discard, tile):
    """**多对子惩罚**：弃牌后若对数 ≤ 2 ⇒ 给正加成（鼓励这样弃）。

    方向依据（§4c-67）：第 8 巡持对数 1~2 时听牌率最高（63~72% / 39~72%），
    **≥3 对时暴跌**（20.8% / 13.0%）。强玩家几乎不出现 ≥3 对 ⇒ 目标是把对数压回 ≤2。
    """
    try:
        pc = _pair_count(rem_after_discard)
        return ROUTE_BONUS if pc <= 2 else 0.0
    except Exception:
        return 0.0

def _pick_discard_route(hand, drawn, exposed, gangs, god_meld=True, view=None,
                        deadline=None, fallback=None):
    """C135 的并列键 + 路线加成（唯一差别）。

    deadline 为可选硬时限：一旦到期，立刻回退到 `fallback`（由调用者给的
    基线弃牌），绝不使用只算了一半的进张数。默认 None 时行为与旧版逐位相同。
    """
    if deadline is not None and fallback is None:
        fallback = _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
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
    if deadline is not None and time.monotonic() >= deadline:
        return fallback
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
        wcnt = 0
        u = 0.0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                wcnt = 0
        else:
            if deadline is not None and time.monotonic() >= deadline:
                return fallback
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld, deadline=deadline)
                if uu[0] is None or uu[1] is None:
                    return fallback
                u = float(uu[0] or 0)
            except Exception:
                if deadline is not None:
                    return fallback
                u = 0.0
            # ★ 唯一的差别：**多对子惩罚** —— 弃牌后对数 ≤2 的选项给正加成（更该弃）。
            #   注意符号：key 用的是 **−u** ⇒ u 越大越优先。
            u += _route_bonus(rem, d)
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC151(SpeedC150):
    """c151 母本；budget_ms=None 时行为不变，set 后由 c187 用作硬时限。"""

    def __init__(self, name="speedc151", budget_ms=None):
        super().__init__(name)
        self.budget_ms = (None if budget_ms is None
                          else max(0.0, float(budget_ms)))

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        deadline = None
        fallback = None
        if self.budget_ms is not None:
            fallback = _best_discard_t(hand, drawn, exposed, gangs,
                                       god_meld=self.GOD_MELD)
            deadline = time.monotonic() + self.budget_ms / 1000.0
        return _pick_discard_route(hand, drawn, exposed, gangs,
                                   god_meld=self.GOD_MELD, view=view,
                                   deadline=deadline, fallback=fallback)
