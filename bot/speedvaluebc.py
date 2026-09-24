# -*- coding: utf-8 -*-
"""SpeedValueBC —— 现役基线 `SpeedValue` + **BC 学到的弃牌排序**（单变量，R1181）。

## 为什么需要它（R1179 / R1180）

役 3 原定"副露后弃牌保真"（meldpost 轴）在**起役前足迹体检**中不合格：
作用面确实有 2,063/21,435（9.6%），但**真改动**是
`speedvalue`→`speedvaluepost` = **0**（全库 0.00%，假阳性陷阱）、
`speedc151`→`speedmeldpost` = 54（0.25%，远低于 10% 足迹门槛）⇒ 役 3 换代。

换代候选 = **BC 弃牌族**（`speedc073w2`，足迹 16.3%）。但它**不能直接当对照臂**：
`speedvalue` → `speedc073w2` 实测 **tile 不同 21.4% + action 不同 0.7%**，
因为它的 MRO 是 `C068Policy → C067Policy → SpeedTUGC → …`（**SpeedTUGC 族**），
而当前基线是 `SpeedValue → SpeedC151 → …`（**c151 族**）⇒ 同时换了"BC 排序"与"底层速度基座"
两条变量（R1141 型复合臂，判词无法归因）。

## 本臂的契约（相对 `SpeedValue` 只多一条变量）

- **决策入口 100% 沿用 `SpeedValue`**：胡 / 自杠 / 抓打圈 / 副露窗口 / 出牌兜底都不碰 ——
  本类**只覆盖 `_pick_discard`**（`SpeedTUGC.decide` 调它的那一处，是唯一的分叉点）；
- **候选构造与 `C067Policy` 逐条对齐**：同为"弃牌后**最小向听**"组、`_pref` 序、`max_candidates=4`，
  且**直接调用同一份** `C067Policy._features` / `C067Policy._score`
  （不复制代码、也不改 `bot/speedc067.py`——那是红线 3 禁止的"改 bot/ 既有文件"）；
- **仅在两条同时成立时改打**：(a) `SpeedValue` 选的那张**落在最小向听组内**（守单变量：只在模型域内替换）、
  (b) 模型给另一张的分数 **严格高过 `margin`**；
- 模型缺失 / 局面不符 / 任何异常 ⇒ **零行为变化**（返回 `SpeedValue` 的原选择）。

## 起役前必须先过"足迹体检"（R1179 硬纪律）

    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluebc --files 300 --phase draw

要求：**作用面 > 0**、**真改动/作用面**有实质量级、**全库占比 ≥ 10%**、**`action 不同` = 0**。
"""
from __future__ import annotations

import collections
import os

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc067 import C067Policy, _Net
from .speedt import _pref
from .speedvalue import SpeedValue

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c073_orig_w2_net.pt")


class SpeedValueBC(SpeedValue):
    """`SpeedValue` + BC 排序（只在"弃后最小向听"组内、且模型严格更优时改打）。"""

    def __init__(self, name="speedvaluebc", model_path=None, margin=0.0,
                 max_candidates=4, shanten_lo=0, shanten_hi=2):
        super().__init__(name=name)
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        # 与 speedc073w2 注册处一致的候选区间 (lo=0, hi=2)
        self.shanten_range = (int(shanten_lo), int(shanten_hi))
        self.stats = collections.Counter()
        path = model_path or os.environ.get("HM_SVBBC_MODEL") or DEFAULT_MODEL
        try:
            self.model = _Net(path)
            self.model_path = path
        except Exception:
            self.model = None
            self.model_path = None

    def _bc_pick(self, hand, exposed, gangs, base):
        """模型在"弃后最小向听组"里的选择；任何时候不成立就返回 `base`（= 零改动）。"""
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            if len(rem) != 13 - 3 * exposed - gangs:
                continue
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs)
            except Exception:
                continue
            cands.append((s, d))
        if not cands:
            return base
        smin = min(s for s, _d in cands)
        if not (self.shanten_range[0] <= smin <= self.shanten_range[1]):
            return base
        group = [d for s, d in cands if s == smin]
        # ★ 单变量闸门：基线不在模型域内时**不动**（否则等于顺带改了基线策略）
        if base not in group:
            return base
        others = sorted([d for d in group if d != base], key=lambda d: (_pref(d, hand), d))
        chosen = ([base] + others)[:self.max_candidates]
        if len(chosen) < 2:
            return base
        # 复用 C067Policy 的同一份特征/打分实现（unbound 调用，我们的实例有同名属性）
        rows = C067Policy._features(self, hand, chosen, base, exposed, gangs)
        if rows is None:
            return base
        try:
            scores = [float(x) for x in C067Policy._score(self, rows)]
        except Exception:
            self.stats["fallback"] += 1
            return base
        if len(scores) != len(chosen):
            self.stats["fallback"] += 1
            return base
        bi = chosen.index(base)
        besti = max(range(len(scores)), key=lambda i: scores[i])
        self.stats["used"] += 1
        if besti != bi and scores[besti] > scores[bi] + self.margin:
            self.stats["changed"] += 1
            return chosen[besti]
        return base

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        if self.model is None or not hand or base not in hand:
            return base
        try:
            return self._bc_pick(hand, exposed, gangs, base)
        except Exception:
            self.stats["fallback"] += 1
            return base
