# -*- coding: utf-8 -*-
"""C068b 学生策略：C068-BC 的「公开可见牌活等」版。

与 C068 的唯一差异：候选特征里的 ukeire live 按「自家手牌 + 弃牌河 + 四家副露」
计算（信息更全），其余（候选集、排序、margin、回退）完全一致。
"""
from __future__ import annotations

import numpy as np

from .c068feat import after_feat_v2, visible_vector
from .speedc067 import C067Policy
from .speedq2 import _state_feat
from .speedtw import _meld_tiles
from mahjong.tiles import id_of


class C068bPolicy(C067Policy):
    def __init__(self, name="speedc068b", model_path=None, margin=0.0,
                 max_candidates=4, lo=1, hi=2):
        super().__init__(name=name, model_path=model_path or "var/c068b_bc_net.pt",
                         margin=margin, max_candidates=max_candidates)
        self.shanten_range = (int(lo), int(hi))

    def _visible(self, view):
        return visible_vector(view.get("river") or [],
                              view.get("all_melds") or [],
                              meld_tiles=_meld_tiles)

    def _features(self, hand, candidates, base, exposed, gangs):
        vis = getattr(self, "_vis", None)
        sb = ab = None
        rows = []
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            si = after_feat_v2(hand, d, exposed, gangs, vis)
            ai = np.zeros(34, dtype=np.float32)
            ai[id_of(d)] = 1.0
            if d == base:
                sb, ab = si, ai
            rows.append((d, si, ai))
        if sb is None or ab is None:
            return None
        return [list(si) + list(ai) + [x - y for x, y in zip(si, sb)] +
                [x - y for x, y in zip(ai, ab)] for _d, si, ai in rows]
