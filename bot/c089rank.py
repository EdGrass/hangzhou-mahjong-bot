# -*- coding: utf-8 -*-
"""C089 候选排序器（共享模块）：训练（var/_c089_ranker_train.py）与在线策略共用。

用途：把「最小向听候选」按「教师更可能选」排序，取 [base] + top3 作为主模型的候选集，
在不增加候选数的前提下把覆盖率从 `_pref` 的 92.66% 提高。
特征（81 维）= _state_feat(弃后手牌)(43) + 牌 onehot(34) + [巡目, 河长, 副露, 杠](4)。
"""
from __future__ import annotations

import numpy as np

from mahjong.tiles import id_of

from .speedq2 import _state_feat

DIM = 81


def cand_row(hand_after, tile, exposed, gangs, river_len):
    one = [0.0] * 34
    one[id_of(tile)] = 1.0
    return list(_state_feat(list(hand_after), exposed, gangs, use_ukeire=True)) + one + [
        min(1.0, (river_len / 4.0) / 12.0), min(1.0, river_len / 24.0),
        exposed / 4.0, gangs / 4.0]


class Ranker:
    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din=DIM, hidden=192):
                super().__init__()
                self.f = nn.Sequential(nn.Linear(din, hidden), nn.ReLU(), nn.Dropout(.1),
                                       nn.Linear(hidden, 96), nn.ReLU(), nn.Dropout(.05),
                                       nn.Linear(96, 32), nn.ReLU(), nn.Linear(32, 1))

            def forward(self, x):
                return self.f(x).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.net = Net(int(blob.get("din", DIM)))
        self.net.load_state_dict(blob["state"])
        self.net.eval()

    def score(self, rows):
        self.torch.set_num_threads(1)
        with self.torch.no_grad():
            return self.net(self.torch.tensor(np.asarray(rows, dtype=np.float32))).numpy()

    def order(self, hand, cand, exposed, gangs, river_len):
        """返回按「教师更可能选」降序排序的候选（评分相同则保持原顺序）。"""
        rows = []
        for d in cand:
            rem = list(hand)
            rem.remove(d)
            rows.append(cand_row(rem, d, exposed, gangs, river_len))
        sc = [float(x) for x in self.score(rows)]
        return [d for _s, d in sorted(zip(sc, cand), key=lambda kv: -kv[0])]
