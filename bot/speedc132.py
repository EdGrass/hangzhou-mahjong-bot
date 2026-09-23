# -*- coding: utf-8 -*-
"""SpeedC132 —— `speedtugc` 的**单变量**候选：弃牌并列时按 **live 进张(ukeire)** 排序。

唯一差异：`SpeedTUGC._pick_discard` 的排序键由
    基线：(向听, −听牌张数[仅听牌时], _pref, 保留摸切)
    本候选：(向听, −听牌张数[仅听牌时], **−live进张**, _pref, 保留摸切)
—— 即**非听牌段不再用静态 `_pref` 打破并列，而是看「打出这张后能进多少张」**。

为什么挑这一条（全部有实测支撑）：
1. 基线 `_best_discard_t` 在 `s>0`（未听牌）时**完全不看进张**：`wcnt` 只在 `s==0` 时计算，
   于是并列全部落到静态 `_pref`。而**未听牌段是绝大多数决策**。
2. 上一轮离线审计（`bot/speedc117.py` docstring，6,000 个真实决策）：
   基线在「最小向听组」内**平均落后最优进张 4.99 张（≈1.25 种牌）**，线上（含学生网）仍落后 4.78 张。
3. 真机画像：我方胡牌速度 **8.74 弃牌/胡**，前列 **8.0–8.3**（慢 ~5%）；摸切率 52.5% vs 场中位 44%。
4. 成本可忽略（实测）：`ukeire_counts` 0.01ms、`exact_shanten` 0.04ms ⇒
   一个决策 <1ms（对比被延迟门禁淘汰的 speedc130 p95≈3s）。

与 `bot/speedc117.py` 的区别：C117 建在 **C068/C073 学生网家族**（那一家族真机 −19.8 分/房），
本候选建在**当前基线 speedtugc** 上 ⇒ 是干净的「只改进张排序」单变量。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.shanten import waits

from .speedtugc import SpeedTUGC
from .speedt import _pref
from .c069routes import ukeire_counts


def _live(rem):
    try:
        _n, live = ukeire_counts(list(rem))
        return float(live)
    except Exception:
        return 0.0


def _best_discard_ukeire(hand, drawn, exposed, gangs, god_meld=True):
    """两趟，省算力：先按向听筛出最小向听组，只在组内算进张。"""
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
    best_key, best_tile = None, None
    for d, rem, s in cands:
        if s != smin:
            continue
        wcnt = 0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                wcnt = 0
        live = 0.0 if s == 0 else _live(rem)
        key = (s, -wcnt, -live, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC132(SpeedTUGC):
    def __init__(self, name="speedc132"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        # ⚠ 本候选已作废（见文件头）：它是按"邻接代理"排序的。保留仅为可导入/可复现。
        return _best_discard_ukeire(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD)
