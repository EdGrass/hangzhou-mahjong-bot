# -*- coding: utf-8 -*-
"""SpeedC152 —— **分档对数奖励出牌**（`speedc151` 的单变量候选）。

与 c151 的**唯一差别**：把 c151 的**平奖励**（`pc<=2` 给同一个 `ROUTE_BONUS`）
换成**按实测曲线分档**的权重。

依据（STATUS §9.26 / §9.35 / §9.38）：
- 「该形状能否给出爆头形」的实测曲线：**pc=0 → 100%、1 → 33.8%、2 → 29.4%、3 → 21.5%、4 → 13.5%、5 → 76.0%**
  ⇒ pc=0 特殊高、**1→4 单调下降**、pc=5 另有七对线；
- c151 用的是「听牌率」的门槛（≤2，§4c-67），而本月主线是**爆头形**（门槛更靠 ≤1，但**不能设硬门槛**：
  pc=1 与 pc=2 只差 4.4pp）；
- 离线 footprint（220 真实局面，§9.38）：

  | 权重方案 | 平均弃后对数 | 分歧率 |
  |---|---|---|
  | plain | 1.950 | — |
  | flat ≤2=8（c151）| 1.868 | — |
  | **mono_hard 12/8/2（本候选）** | **1.814** | **15.5%** |
  | p01_only 12/12/0 | 1.818 | 21.4%（**同结果却更多干预 ⇒ 被支配**）|
  | p5_bonus（+pc5=6）| 1.836 | 6.8%（**本采样无差异 ⇒ 先不加**）|

⇒ **定参 `W = {0: 12.0, 1: 8.0, 2: 2.0}`**（pc≥3 得 0）。
护栏：仍是**并列项**（主键 = 向听）⇒ 下行有界；**不得牺牲 C036**（跑 `giveup_audit` 复核）。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc150 import SpeedC150
from .speedc135 import _pref
from .ukeire import real_ukeire, visible_counts

# ★ 唯一旋钮：分档权重（pc → 进张加成）。pc>=3 不在表里 ⇒ 0。
W_GRADED = {0: 12.0, 1: 8.0, 2: 2.0}


def _pair_count(hand):
    """手牌里的对数（≥2 张的牌型数）——与 c151 同定义。"""
    try:
        import collections as _c
        return sum(1 for v in _c.Counter(hand).values() if v >= 2)
    except Exception:
        return 0


def _route_bonus(rem_after_discard, tile):
    """**分档**路线加成：按「该形状能否给出爆头形」的实测曲线给权。

    方向：u 越大越优先（key 用 −u）⇒ pc=0 最大、1 次之、2 再次、≥3 为 0。
    """
    try:
        return float(W_GRADED.get(_pair_count(rem_after_discard), 0.0))
    except Exception:
        return 0.0


def _pick_discard_graded(hand, drawn, exposed, gangs, god_meld=True, view=None):
    """C151 的并列键 + **分档**路线加成（与 c151 只差 `_route_bonus`）。"""
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
        wcnt = 0
        u = 0.0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                wcnt = 0
        else:
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception:
                u = 0.0
            # ★ 唯一差别：**分档**加成（c151 是平的 `pc<=2 ⇒ 同一分`）。
            #   注意符号：key 用 **−u** ⇒ u 越大越优先。
            u += _route_bonus(rem, d)
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC152(SpeedC150):
    def __init__(self, name="speedc152"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_graded(hand, drawn, exposed, gangs,
                                    god_meld=self.GOD_MELD, view=view)
