# -*- coding: utf-8 -*-
"""SpeedC151BC —— `SpeedC151` + **BC 学到的弃牌排序**（役 3 的**分支臂**，R1198）。

## 为什么需要它

役 3 预登记（`prereg-campaign3-speedvaluebc-20260924.md`）的**分支 A** 是
"役 2 采用 `speedvalue` ⇒ 役 3 = `speedvalue` → `speedvaluebc`"。
但役 2 的判词有**三条分支**（采用 / 平 / 负）。若役 2 **不采用** `speedvalue`（基线仍是 `speedc151`），
则 `speedvaluebc`（底是 SpeedValue）就成了**跨基线**的对照 ⇒ 判词无法归因。

本臂补上**分支 B**：把同一套 BC 排序接到 **`SpeedC151`** 上 ⇒ 无论役 2 走哪一支，役 3 都有**单变量臂**。

## 契约（相对 `speedc151` 只多一条变量）

- **只覆盖 `_pick_discard`**：胡/自杠/抓打圈/副露窗口 100% 沿用 `SpeedC151`；
- 基线 = `SpeedC151._pick_discard`（其自身选择），只在 **① 基线所选落在"弃后最小向听"组内**
  且 **② 模型分数严格高过 `margin`** 时才改打；
- 与 `bot/speedvaluebc.py` **同一套**候选构造与特征/打分（直接 unbound 调用 `C067Policy._features/_score`）；
- 模型缺失/异常 ⇒ **零行为变化**。

## 起役前必须做（R1186 纪律）

    python -X utf8 tools/offline_replay.py --base speedc151 --cand speedc151bc --files 300 --phase draw --lowprio

要求：**该阶段**全库占比 ≥10% 且 **action 差异 = 0**；模型在场断言见 §5 起役清单。
"""
from __future__ import annotations

import collections
import os

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc067 import C067Policy, _Net
from .speedc151 import SpeedC151
from .speedt import _pref

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c073_orig_w2_net.pt")


class SpeedC151BC(SpeedC151):
    """`SpeedC151` + BC 排序（只在"弃后最小向听"组内、且模型严格更优时改打）。"""

    def __init__(self, name="speedc151bc", model_path=None, margin=0.0,
                 max_candidates=4, shanten_lo=0, shanten_hi=2):
        super().__init__(name=name)
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        self.shanten_range = (int(shanten_lo), int(shanten_hi))
        self.stats = collections.Counter()
        path = model_path or os.environ.get("HM_C151BC_MODEL") or DEFAULT_MODEL
        try:
            self.model = _Net(path)
            self.model_path = path
        except Exception:
            self.model = None
            self.model_path = None

    def _bc_pick(self, hand, exposed, gangs, base):
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
        if base not in group:                 # 单变量闸门：基线不在模型域内时不动
            return base
        others = sorted([d for d in group if d != base], key=lambda d: (_pref(d, hand), d))
        chosen = ([base] + others)[:self.max_candidates]
        if len(chosen) < 2:
            return base
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
