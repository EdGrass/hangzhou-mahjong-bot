# -*- coding: utf-8 -*-
"""C068e 学生策略：C068 家族多模型集成（同特征口径的 logit 平均）。

用于压低单模型方差：成员均使用 C067 的 154 维「相对基线优势」特征，
只有训练语料/损失/候选区间不同（M2 对齐重训 / C068 扩容 / lo0 含听牌段）。
"""
from __future__ import annotations

import os

from .speedc067 import _Net
from .speedc068 import C068Policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATHS = (
    os.path.join(ROOT, "var", "_c068_sanity_tie_net.pt"),
    os.path.join(ROOT, "var", "c068_bc_net.pt"),
    os.path.join(ROOT, "var", "c068_bc_lo0_net.pt"),
)


class _Ensemble:
    def __init__(self, nets):
        self.nets = list(nets)

    def score(self, rows):
        acc = None
        for n in self.nets:
            s = n.score(rows)
            acc = s if acc is None else acc + s
        return acc / max(1, len(self.nets))


class C068ePolicy(C068Policy):
    def __init__(self, name="speedc068e", model_paths=None, margin=0.0,
                 max_candidates=4, lo=0, hi=2):
        paths = list(model_paths or DEFAULT_PATHS)
        super().__init__(name=name, model_path=paths[0], margin=margin,
                         max_candidates=max_candidates, lo=lo, hi=hi)
        nets = []
        for p in paths:
            try:
                nets.append(_Net(p))
            except Exception:
                continue
        self.members = len(nets)
        self.model = _Ensemble(nets) if nets else None
