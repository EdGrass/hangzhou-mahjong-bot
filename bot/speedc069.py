# -*- coding: utf-8 -*-
"""C069 学生策略：C068-lo0 + 目标牌型（route）特征。

特征 = 在线 _state_feat(43) + c069routes.route_feats(22) = 65/候选，
行 = [候选65, 动作34, 候选−基线差65, 动作差34] → din=198（与 var/_c069_discard_train.py 同源）。
弃牌候选集/截断/margin 与 C068 一致；胡/抓打圈/副露窗口回退 C045。
"""
from __future__ import annotations

import os

import numpy as np

from mahjong.tiles import id_of

from .c069routes import route_feats
from .speedc067 import C067Policy
from .speedc068 import C068Policy
from .speedq2 import _state_feat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c069_bc_net.pt")


def cand_feat(hand, d, exposed, gangs):
    """单候选特征（训练 var/_c069_discard_train.py:feat 的在线等价实现）。"""
    rem = list(hand)
    rem.remove(d)
    return np.asarray(list(_state_feat(rem, exposed, gangs, use_ukeire=True))
                      + list(route_feats(rem, exposed, gangs)), dtype=np.float32)


class C069Policy(C068Policy):
    def __init__(self, name="speedc069", model_path=None, margin=0.0,
                 max_candidates=4, lo=0, hi=2, cand_order="pref"):
        super().__init__(name=name, model_path=model_path or DEFAULT_MODEL,
                         margin=margin, max_candidates=max_candidates, lo=lo, hi=hi,
                         cand_order=cand_order)

    def _features(self, hand, candidates, base, exposed, gangs):
        sb = ab = None
        rows = []
        for d in candidates:
            si = cand_feat(hand, d, exposed, gangs)
            ai = np.zeros(34, dtype=np.float32)
            ai[id_of(d)] = 1.0
            if d == base:
                sb, ab = si, ai
            rows.append((d, si, ai))
        if sb is None or ab is None:
            return None
        return [list(si) + list(ai) + [x - y for x, y in zip(si, sb)] +
                [x - y for x, y in zip(ai, ab)] for _d, si, ai in rows]
