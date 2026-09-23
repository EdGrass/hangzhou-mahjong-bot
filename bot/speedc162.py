# -*- coding: utf-8 -*-
"""SpeedC162 —— **保对子档**（c152 的**反向**候选；本役的一条"方向测试"臂）。

**为什么做它（2026-09-17 两条新证据，与既有 §4c-67 直接冲突 —— 这就是要上真机的原因）**：
1. **同房出牌对照**（`var/_strong_discard_vs_policy.py`，3,038 个强者 draw 决策）：**分歧 33.5%**；分歧时
   **我方**：真进张 **31.37**、弃后对数 **2.055**；**强者**：真进张 **27.24**、弃后对数 **2.441**
   ⇒ **他们牺牲进张、保留更多对子**；我们反过来（保进张、拆对）。
2. **外生分桶**（起手对数 ← 随机发牌，600 场）：强者在**每个**起手对数桶都赢更多，且**对数越多赢率越高**
   （0 对 25.6% → 1 对 27.1% → 2 对 **29.7%** → 3 对 **30.8%**），而我方曲线更平（20.5/24.8/23.2/26.5/22.7），
   **最大单桶差距在"2 对"（+6.5pp）** —— 2 对正是"路线选择"（七对/碰/门清）最关键、也是最常见的档。
3. **冲突方**：`§4c-67` 实测"持对数与 8 巡听牌强负相关"（c151/c152"压对数"的依据）。但 §0★★★ 已证
   **听牌速度与得分无单调关系** ⇒ "为听牌而拆对"可能是在优化代理指标。
⇒ 因此本役**同时放 c152（压对数）与 c162（保对子）**，让真机给出方向答案。

**实现**（与 c152 同构，唯一差别是分档方向）：
    c152：`bonus = W_GRADED[pc(rem)]`，`W={0:12,1:8,2:2}` ⇒ 越少对子越优；
    **c162：`bonus = KP[pc(rem)]`，`KP={0:0,1:2,2:8,3:12,4:12,5:12}`** ⇒ 越多对子越优（pc≥5 是七对线，给满）。
仍是**并列项**（主键 = 向听）⇒ 下行有界；仍不得牺牲 C036（跑 giveup_audit 复核）。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc150 import SpeedC150
from .speedc135 import _pref
from .ukeire import real_ukeire, visible_counts

# ★ 唯一旋钮：保对子分档（pc → 进张加成）；pc≥5 直接给满（七对线）
KP_KEEP = {0: 0.0, 1: 2.0, 2: 8.0, 3: 12.0, 4: 12.0, 5: 12.0}


def _pair_count(hand):
    try:
        import collections as _c
        return sum(1 for v in _c.Counter(hand).values() if v >= 2)
    except Exception:
        return 0


def _route_bonus_keep(rem):
    return KP_KEEP.get(min(5, _pair_count(rem)), 12.0)


def _pick_discard_keep_pairs(hand, drawn, exposed, gangs, god_meld=True, view=None):
    """c152 的同构版本：主键/其余项完全一致，只把路线加成换成"保对子"。"""
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
            u += _route_bonus_keep(rem)
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC162(SpeedC150):
    def __init__(self, name="speedc162"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_keep_pairs(hand, drawn, exposed, gangs,
                                        god_meld=self.GOD_MELD, view=view)
