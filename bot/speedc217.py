# -*- coding: utf-8 -*-
"""SpeedC217 —— `c211` **去掉 c135**（弃牌路径回到 `speedtugc` 的 `_best_discard_t`）。

动机（R632）：把 c211 的四类成分的"真机符号"拆开。
- 已知真机读数（不同窗口，慎读）：
  | 臂 | 成分 | 分/席局 |
  |---|---|---:|
  | speedtugc | —（老基线） | **−0.188** |
  | **speedc135** | 只有"真进张弃牌" | **−0.418** |
  | speedc146 | 杠/自杠/吃碰/财飘（**不含 c135**） | −0.439 |
  | speedc152 | c146 + c135 + route bonus | −0.356 |
  | **speedc211** | c152 去掉 C136 | **−0.312** |
- ⇒ **c135 单独用时是最差之一（−0.418）**，但它的进张命中率是 99%（过程侧最优）
  ⇒ 强烈怀疑 **c135 用"番值"换了"胡率"，净效应为负**。
- 本候选 = **c211 完全去掉 c135 的弃牌路径**（`_pick_discard` 回到 `SpeedTUGC._best_discard_t`），
  其余（C144 明杠 / C134 自杠 / C141 财飘 / 去掉 C136 的严格门控 / route bonus 也不再参与）不变。

⚠ **注意 route bonus 是挂载在 c151/c152 的 `_pick_discard` 里的**，
   所以本候选同时去掉了它 —— 这在 R579（c213）里已被测为**中性**，影响可忽略。

用法：等 c211 的 100 房跑完后，用 `_rollout_ev` / `_rollout_meld_ev` 测它与 c211 的差，
再决定要不要占真机工位。
"""
from __future__ import annotations

from .speedc211 import SpeedC211
from .speedt import _best_discard_t


class SpeedC217(SpeedC211):
    def __init__(self, name="speedc217"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        # ★ 唯一差别：回到基线的弃牌路径（不含 c135 的真进张 / 不含 route bonus）
        return _best_discard_t(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD)
