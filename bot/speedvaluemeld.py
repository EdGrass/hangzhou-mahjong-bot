# -*- coding: utf-8 -*-
"""SpeedValueMeld —— 现役基线 `SpeedValue` + **学习到的选择性副露**（单变量，R1190）。

## 为什么

R1186/R1189 的保真足迹体检给出**当前唯一两个过关的轴**：
  · draw（出牌）层：`speedvaluebc` 15.9% ⇒ 役 3 定案；
  · window（索取）层：`speedc188` 形态 12.7%（索取率 67.6%→77.4%、严格超集）⇒ 役 4 候选。

但 `speedc188` 的 MRO 是 `c188 → c186 → c156 → c151`，与现役基线 `SpeedValue → c151` **不同族底**，
直接对照就是"复合臂"（判词无法归因）。进一步实测 **`c151 → c156` 的 draw 层足迹 = 0.0%（21,424 决策 100% 一致）**
⇒ **`c156` 只作用于索取层**（它自述也正是"唯一差别 = `_want_claim`"）。

## 本臂契约（相对 `speedvalue` 只多一条变量）

- **只覆盖 `_want_claim`**：出牌（`_pick_discard`）、胡、杠、抓打圈全部沿用 `SpeedValue`；
- **不否决任何基线索取**：基线 `_want_claim` 说"要" ⇒ 直接要（**单向增加，下行有界**）；
- 基线说"不要"时，用**同一个**学习副露网（`var/c121_meld_net.pt`，141 维窗口特征）
  按 `claim_p`（默认 0.60）补一部分"要"；
- 逻辑与 `bot/speedc156.py` 的 `SpeedC156._want_claim` **逐行等价**（`super()` 链在本 MRO 下同样落在
  `SpeedC144._want_claim`，即与 c156 的基线门控一致）——因为红线 3 禁止改 `bot/` 既有文件，
  这里**照抄该 12 行**并在测试里与 `SpeedC156` 做**行为等价断言**防漂移。

## 起役前足迹体检（R1186 纪律：分阶段）

    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluemeld --phase window  # 期望 ≈12.7% 可索取窗口
    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluemeld --phase draw    # 期望 0.0%
"""
from __future__ import annotations

import os

from .c121meld import window_features
from .speedc121 import _MeldNet
from .speedvalue import SpeedValue

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MELD = os.path.join(ROOT, "var", "c121_meld_net.pt")


class SpeedValueMeld(SpeedValue):
    """`SpeedValue` + 学习到的选择性副露（只加、不减、单变量）。"""

    def __init__(self, name="speedvaluemeld", claim_p=0.60, meld_path=DEFAULT_MELD):
        super().__init__(name=name)
        self.claim_p = float(claim_p)
        try:
            self._mnet = _MeldNet(meld_path)
        except Exception:
            self._mnet = None          # 模型缺失 ⇒ 退回纯 SpeedValue（零行为变化）

    def _want_claim(self, view, kind, pair=None):
        # 与 bot/speedc156.py::SpeedC156._want_claim 逐行等价（见模块 docstring 的说明）
        if super()._want_claim(view, kind, pair):
            return True                # 基线已要 ⇒ 直接要（本臂不否决任何基线索取）
        if self._mnet is None:
            return False
        try:
            offer = view.get("offer_tile")
            if not offer:
                return False
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            feat = window_features(hand, melds, list(view.get("river") or []),
                                   view.get("all_melds") or [], offer, kind)
            p = float(self._mnet.prob([feat])[0])
        except Exception:
            return False
        return p >= self.claim_p
