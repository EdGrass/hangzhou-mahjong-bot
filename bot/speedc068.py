# -*- coding: utf-8 -*-
"""C068 学生策略：C067-BC 的扩容版（更多顶级教师 + 全量复盘语料）。

差异只在模型与候选区间：
  - 默认模型 var/c068_bc_net.pt（C068 语料训练）
  - shanten_range 可扩到 (0,2)，把「弃牌后即听牌」的决策也交给模型排序
其余（胡/抓打圈/副露窗口）全部回退 C045/SpeedTUGC。模型缺失时零行为变化。
"""
from __future__ import annotations

import os

from .speedc067 import C067Policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c068_bc_net.pt")


class C068Policy(C067Policy):
    def __init__(self, name="speedc068", model_path=None, margin=0.0,
                 max_candidates=4, lo=1, hi=2, cand_order="pref"):
        super().__init__(name=name, model_path=model_path or DEFAULT_MODEL,
                         margin=margin, max_candidates=max_candidates,
                         cand_order=cand_order)
        self.shanten_range = (int(lo), int(hi))
