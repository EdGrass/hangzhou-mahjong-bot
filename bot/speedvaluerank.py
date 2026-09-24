# -*- coding: utf-8 -*-
"""SpeedValueRank —— 现役基线 `SpeedValue` + **教师候选排序器**（`bot/c089rank.Ranker`，单变量，R1207）。

## 为什么（R1206）

R1202 用"共同起点"证明：**同一中盘状态（同向听、同巡）下，我们到 k7 的听牌率比 top32 低 5~7pp**
⇒ 差距在**单步 ukeire 指标看不到的地方**（我们的单步最优命中率其实已追平 top32）。
而项目里 `bot/speedc215.py` 的自述**正好瞄准这一点**："把并列 tiebreak 从静态 `_pref`
换成**教师候选排序器**（81 维，学'顶级玩家会弃哪张'）"，动机原文即"**起手 2~3 向听的中等手牌能否越过听牌线**"。
`speedc215` 相对其祖先 `c152` 的**保真足迹 = 23.3%（4,989/21,418，action 差异 0）** ⇒ 宽足迹、方向在靶。

但 `speedc215` 的族底是 `c211 → c152 → c150`（**不含 c151**），与现役基线 `SpeedValue → c151` 不同族底
⇒ 直接对照是**复合臂**。本类把**同一个 81 维排序器**接到**现役基线**上，做成"只多一条变量"的干净臂。

## 契约（相对 `speedvalue` 只多一条）

- **只覆盖 `_pick_discard`**：胡/自杠/抓打圈/副露窗口 100% 沿用 `SpeedValue`；
- 基线 = `SpeedValue._pick_discard` 自己的选择；**单变量闸门**：基线所选必须落在"**弃后最小向听组**"内才动；
- 只在**同一最小向听组内**用 `Ranker` 重排，且**只有排序器的分数严格高过基线**（`margin`，默认 0.0）才改打；
- 排序器缺失/异常/局面不符 ⇒ **零行为变化**。

## 起役前足迹体检（R1186 纪律）

    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluerank --files 300 --phase draw --lowprio
"""
from __future__ import annotations

import collections
import os

from mahjong.shanten_exact import shanten as exact_shanten

from .c089rank import Ranker, cand_row
from .speedvalue import SpeedValue

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RANKER = os.path.join(ROOT, "var", "c089_ranker_net.pt")


class SpeedValueRank(SpeedValue):
    """`SpeedValue` + 81 维教师排序器（只在"弃后最小向听组"内、且排序器严格更优时改打）。"""

    def __init__(self, name="speedvaluerank", ranker_path=None, margin=0.0, god_meld=None):
        super().__init__(name=name)
        self.margin = float(margin)
        if god_meld is not None:
            self.GOD_MELD = bool(god_meld)
        self.stats = collections.Counter()
        try:
            self.ranker = Ranker(ranker_path or DEFAULT_RANKER)
        except Exception:
            self.ranker = None

    def _min_shanten_group(self, hand, exposed, gangs):
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            if len(rem) != 13 - 3 * exposed - gangs:
                continue
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs, god_meld=self.GOD_MELD)
            except Exception:
                continue
            cands.append((s, d))
        if not cands:
            return []
        smin = min(s for s, _d in cands)
        return [d for s, d in cands if s == smin]

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        if self.ranker is None or not hand or base not in hand:
            return base
        try:
            group = self._min_shanten_group(hand, exposed, gangs)
            if base not in group:                     # ★ 单变量闸门：基线不在模型域内 ⇒ 不动
                return base
            river_len = int(view.get("river_len") or len(view.get("river") or [])) if view else 0
            order = self.ranker.order(hand, [base] + [d for d in group if d != base],
                                      exposed, gangs, river_len)
            pick = order[0] if order else base
            if pick == base or pick not in hand:
                return base
            # margin 闸门：需要"排序器给 pick 的分数严格高过 base"（默认 0.0 ⇒ 严格更高即可）
            rem_b = list(hand); rem_b.remove(base)
            rem_p = list(hand); rem_p.remove(pick)
            rows = [cand_row(rem_b, base, exposed, gangs, river_len),
                    cand_row(rem_p, pick, exposed, gangs, river_len)]
            sc = [float(x) for x in self.ranker.score(rows)]
            self.stats["used"] += 1
            if sc[1] > sc[0] + self.margin:
                self.stats["changed"] += 1
                return pick
            return base
        except Exception:
            self.stats["fallback"] += 1
            return base
