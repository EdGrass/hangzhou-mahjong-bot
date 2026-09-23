# -*- coding: utf-8 -*-
"""SpeedC160 —— **c156 + 「保白副露」**（单变量：只再加一条副露门控）。

**依据（2026-09-17 新实测，`var/_strong_meld_vs_gate.py --games 400`）**：
把**强者实际完成的吃/碰** 5,067 次，用**当时的现场**（他的手牌/副露/河）问我方门控（c151/C136）：

| 分组 | 次数 | ukeire 变化 | **含白比例** | 巡目 |
|---|---|---|---|---|
| 我方也会要 | 4,314（85.1%） | −5.26 | **0.37** | 4.30 |
| **我方门控不要** | **753（14.9%）** | **−7.76** | **0.63** | **7.05** |

⇒ **我们漏掉的不是"随便放宽"，而是一类特定的副露**：**手上有白（34 号牌，爆头/四白的票）、中盘偏晚、
以"真进张"口径看是负收益**——而"真进张/向听"这套指标**本来就不描述爆头形**（爆头 = 摸任意张皆胡，
不需要进张）。强者的做法是：**用副露把面子做满，同时把白留成"万能票"**。

**本臂与 `speedc156` 的唯一差别**：在 c156（含学习网）**说"不要"**的窗口上，若同时满足
  ① 手上有白 **且这次吃/碰不吃掉白**（白是票，不能打出去）；
  ② 牌河长度 ≥ `min_river`（中盘偏晚；证据：被漏掉那组巡目均值 7.05）； 
  ③ 吃/碰后**向听不变差**（不许把牌做坏）；
  ④ **真进张损失 ≤ `max_loss`**（证据：被漏掉那组均值 −7.76 → 默认 8）
⇒ 则接受。**仍是单向增加**（绝不否决 c156/基线的任何一次索取）。

参数化（便于脚印扫描）：`min_river`、`max_loss`。判据与队列同：机制（有副露局占比/8 巡听牌/番/爆头）
+ `tools/ab_readout.py` 净胜/房（150 房/臂、t≥1.5）。
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc156 import DEFAULT_MELD, SpeedC156
from .ukeire import visible_counts

BAI = "白"


class SpeedC160(SpeedC156):

    def __init__(self, name="speedc160", claim_p=0.60, meld_path=DEFAULT_MELD,
                 min_river=20, max_loss=8.0):
        super().__init__(name, claim_p=claim_p, meld_path=meld_path)
        self.min_river = int(min_river)
        self.max_loss = float(max_loss)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True                      # c156（含学习网）已要 ⇒ 直接要（本臂不否决任何索取）
        try:
            offer = view.get("offer_tile")
            hand = list(view.get("my_hand") or [])
            if not offer or BAI not in hand:
                return False                 # ① 白是票：手上没有白就不属于这一类
            rl = view.get("river_len")
            if rl is None:
                rl = len(view.get("river") or [])
            if int(rl) < self.min_river:
                return False                 # ② 中盘偏晚（证据 mean 巡目 7.05）
            melds = view.get("melds") or []
            e = len(melds)
            g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
            if len(hand) != 13 - 3 * e - g:
                return False
            vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            before = _state(hand, e, g, vis, self.GOD_MELD)
            if before is None or before[1] is None:
                return False
            if kind == "chi":
                opts = [("chi", p) for p in _chi_pairs(hand, offer)]
            else:
                opts = [(kind, None)]
            for k, p in opts:
                used = list(p) if k == "chi" else [offer, offer]
                if BAI in used:
                    continue                 # ① 不许把白吃/碰出去
                after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
                if after is None or after[1] is None:
                    continue
                if after[0] > before[0]:
                    continue                 # ③ 向听不许变差
                if after[1] < before[1] - self.max_loss:
                    continue                 # ④ 进张损失有界
                return True
            return False
        except Exception:
            return False
