# -*- coding: utf-8 -*-
"""C076 学生策略：**状态价值贪心**（V(s) = P(本局我胡)）取代行为克隆打分。

- 对每个最小向听候选弃牌，计算「弃后局面」的价值 V，取最大者；
- 只有当 V(best) > V(基线) + margin 时才偏离 C045 基线（margin 单位 = logit）；
- 弃牌之外（胡/抓打圈/副露）100% 回退 C045；模型缺失时零行为变化。

特征与训练（var/_c076_value_train.py）严格同源：
  _state_feat(弃后手牌, 副露, 杠, use_ukeire=True) 43 维
  + [巡目(河长/4)/12, 河长/24, 副露/4, 杠/4] = 47 维（巡目用河长推算 → 在线可精确复现）
"""
from __future__ import annotations

import os

import numpy as np

from .speedc068 import C068Policy
from .speedq2 import _state_feat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VALUE = os.path.join(ROOT, "var", "c076_value_net.pt")
DEFAULT_BASE = os.path.join(ROOT, "var", "c068_bc_lo0_net.pt")


class _VNet:
    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din=47, hidden=192):
                super().__init__()
                self.f = nn.Sequential(nn.Linear(din, hidden), nn.ReLU(), nn.Dropout(.1),
                                       nn.Linear(hidden, 96), nn.ReLU(), nn.Dropout(.05),
                                       nn.Linear(96, 32), nn.ReLU(), nn.Linear(32, 1))

            def forward(self, x):
                return self.f(x).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.net = Net(int(blob.get("din", 47)))
        self.net.load_state_dict(blob["state"])
        self.net.eval()

    def score(self, rows):
        self.torch.set_num_threads(1)
        with self.torch.no_grad():
            return self.net(self.torch.tensor(np.asarray(rows, dtype=np.float32))).numpy()


class C076Policy(C068Policy):
    def __init__(self, name="speedc076", value_path=None, base_model=None,
                 margin=0.05, max_candidates=4, lo=0, hi=2):
        super().__init__(name=name, model_path=base_model or DEFAULT_BASE,
                         margin=margin, max_candidates=max_candidates, lo=lo, hi=hi)
        self.river_len = 0
        try:
            self.model = _VNet(value_path or DEFAULT_VALUE)
            self.value_path = value_path or DEFAULT_VALUE
        except Exception:
            self.model = None
            self.value_path = None

    def _visible(self, view):
        self.river_len = len(view.get("river") or [])
        return None

    def _features(self, hand, candidates, base, exposed, gangs):
        rl = float(self.river_len)
        rows = []
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            rows.append(list(_state_feat(rem, exposed, gangs, use_ukeire=True)) + [
                min(1.0, (rl / 4.0) / 12.0), min(1.0, rl / 24.0),
                exposed / 4.0, gangs / 4.0])
        return rows
