# -*- coding: utf-8 -*-
"""C089 学生策略：C068/W4 + **学到的候选排序器**。

差异只有一处：把「最小向听候选里除 base 之外的排序」从静态 `_pref` 换成
`bot/c089rank.Ranker`（学「顶级教师会弃哪张」的 per-tile 打分）→ 在不增加候选数的前提下
把「教师选择落在候选集内」的比例从 92.66% 提高；主模型与权重（w=4）保持不变。
排序器缺失时行为与 C068 完全一致。
"""
from __future__ import annotations

import os

from .c089rank import Ranker
from .speedc068 import C068Policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RANKER = os.path.join(ROOT, "var", "c089_ranker_net.pt")


class C089Policy(C068Policy):
    def __init__(self, name="speedc089", model_path=None, order_path=None, margin=0.0,
                 max_candidates=4, lo=0, hi=2):
        super().__init__(name=name, model_path=model_path, margin=margin,
                         max_candidates=max_candidates, lo=lo, hi=hi)
        try:
            self.ranker = Ranker(order_path or DEFAULT_RANKER)
            self.order_path = order_path or DEFAULT_RANKER
        except Exception:
            self.ranker = None
            self.order_path = None

    def _order_others(self, hand, group, base, view, pref_key):
        others = [d for d in group if d != base]
        if self.ranker is None or len(others) < 2:
            return sorted(others, key=pref_key)
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if m.get("type") == "gang")
        rl = float(len(view.get("river") or []))
        try:
            ordered = self.ranker.order(hand, others, exposed, gangs, rl)
            return ordered if ordered else sorted(others, key=pref_key)
        except Exception:
            return sorted(others, key=pref_key)
