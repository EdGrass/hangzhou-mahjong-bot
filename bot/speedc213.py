# -*- coding: utf-8 -*-
"""SpeedC213 —— c211 的**单变量减法**：去掉 c151/c152 的"分档路线加成"（`W_GRADED`）。

依据（2026-09-19 `var/_what_they_buy.py`，600 文件）：
  在"实际弃牌不是最大真进张"的点上，双方都是**多留对子**：
    | 组 | 有损点 | Δ对数（实际−最优） |
    |---|---:|---:|
    | 我们 | 1,820 | **+0.220** |
    | top32 | 434 | **+0.194** |
  而 c152 的 route bonus 是 `pc=0/1/2 → +12/8/2`（**pc 越小越优先 ⇒ 鼓励拆对**），
  方向与"强者在多留对子"相反。本候选把它去掉，回到 c135 的纯真进张排序。

注：c151 的原始依据（STATUS §4c-67）是"持对数与听牌率强负相关"（相关），
而本工具给的是"在同状态、同进张层内，强者选择的方向"（条件对比）——
两者若冲突，按项目纪律（R545/R570）**以自体内轨迹级证据为准**，所以必须实测。
"""
from __future__ import annotations

from .speedc211 import SpeedC211
from .speedc135 import _best_discard_realukeire


class SpeedC213(SpeedC211):
    def __init__(self, name="speedc213"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _best_discard_realukeire(hand, drawn, exposed, gangs,
                                        god_meld=self.GOD_MELD, view=view)
