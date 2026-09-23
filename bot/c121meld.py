# -*- coding: utf-8 -*-
"""C121 副露窗口特征（与 var/_c120b_extract.py 完全同构，141 维）。"""
from __future__ import annotations

import numpy as np

from mahjong.tiles import TILE_IDS, counts_of

TILES = [t for t in sorted(TILE_IDS, key=lambda t: TILE_IDS[t])] + ['白']
IDX = {t: i for i, t in enumerate(TILES)}
GOD = '白'


def vec(cnt_like):
    return np.asarray(counts_of(list(cnt_like)), dtype=np.float32)


def meld_own_counts(melds):
    own = np.zeros(3, dtype=np.float32)
    for m in melds or []:
        if isinstance(m, dict):
            kind = m.get('type')
            tiles = m.get('tiles') or []
            if kind == 'chi':
                own[0] += 1
            elif kind == 'peng':
                own[1] += 1
            elif kind == 'gang':
                own[2] += 1
            elif len(tiles) == 4:
                own[2] += 1
            elif len(tiles) == 3:
                own[0 if (tiles[0] != tiles[1]) else 1] += 1
        elif isinstance(m, (list, tuple)) and len(m) == 3:
            own[0 if m[0] != m[1] else 1] += 1
        elif isinstance(m, (list, tuple)) and len(m) == 4:
            own[2] += 1
    return own


def all_melds_counter(all_melds):
    am = []
    for seat_melds in (all_melds or []):
        for m in (seat_melds or []):
            if isinstance(m, dict):
                tiles = m.get('tiles') or ([m.get('tile')] * 3 if m.get('tile') else [])
            else:
                tiles = list(m)
            am.extend([t for t in tiles if t])
    return am


def window_features(hand, melds, river, all_melds, offer, kind):
    """kind ∈ {'peng','chi','gang_ming'}；返回 141 维向量（与训练语料同构）。"""
    e2 = len(melds or [])
    g2 = sum(1 for m in (melds or []) if (m.get('type') if isinstance(m, dict) else None) == 'gang'
             or (isinstance(m, (list, tuple)) and len(m) == 4))
    rv = list(river or [])
    if offer in rv:
        rv.remove(offer)                      # 与抽取器一致：牌河不含当前提供牌
    own = meld_own_counts(melds)
    am = all_melds_counter(all_melds)
    one = np.zeros(34, dtype=np.float32)
    one[IDX[offer]] = 1.0
    ka = 1.0 if kind == 'peng' else (2.0 if kind == 'chi' else 0.0)
    return np.concatenate([vec(hand), own, vec(rv), vec(am), one,
                           np.array([len(rv) / 40.0, ka], dtype=np.float32)])
