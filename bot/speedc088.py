# -*- coding: utf-8 -*-
"""C088 学生策略：C068 系列 + **花色置换 TTA**（测试时增强）。

思路：麻将 w/b/t 三花色在规则上完全对称，但我们的 MLP 直接吃 34 维计数向量、只见过
「实际花色分配」的样本 → 对「同一副牌换个花色」会给出不同分数（虚假的花色偏好）。
TTA：把每条候选行的 [状态计数块 / 动作 onehot / 状态差分计数块 / 动作差分 onehot]
按 6 种花色置换分别打分并取平均，等价于在推断期做对称化，无需重训。
"""
from __future__ import annotations

import itertools

import numpy as np

from .speedc068 import C068Policy

BLOCKS = ((0, 34), (43, 77), (77, 111), (120, 154))


def suit_perms():
    out = []
    for p in itertools.permutations((0, 1, 2)):
        idx = list(range(34))
        for target, src in enumerate(p):
            for k in range(9):
                idx[target * 9 + k] = src * 9 + k
        out.append(idx)
    return out


class C088Policy(C068Policy):
    def __init__(self, name="speedc088", model_path=None, margin=0.0,
                 max_candidates=4, lo=0, hi=2, tta=True):
        super().__init__(name=name, model_path=model_path, margin=margin,
                         max_candidates=max_candidates, lo=lo, hi=hi)
        self.tta = bool(tta)
        self.perms = suit_perms()

    def _permute(self, rows, idx):
        r = np.array(rows, dtype=np.float32, copy=True)
        a = np.asarray(idx)
        for s0, s1 in BLOCKS:
            r[:, s0:s1] = r[:, s0 + a]
        return r

    def _score(self, rows):
        if not self.tta:
            return self.model.score(rows)
        acc = None
        for idx in self.perms:
            sc = self.model.score(self._permute(rows, idx) if idx != self.perms[0] else rows)
            acc = sc if acc is None else acc + sc
        return acc / float(len(self.perms))
