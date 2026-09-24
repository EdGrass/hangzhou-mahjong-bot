# -*- coding: utf-8 -*-
"""C068b 特征：与 speedq2._state_feat 同构（43 维），但「活等」按公开可见牌修正。

差异仅一处：ukeire 的 live（剩余张数）从「只扣自家手牌」改为
「扣自家手牌 + 弃牌河 + 四家副露」，其余 41 维完全一致。
训练脚本与在线策略共用本模块，保证训练/在线特征严格同源。
"""
from __future__ import annotations

from mahjong.tiles import id_of, is_suit_tile, suit_and_num

from .speedq2 import _state_feat
from .speedt import _pref  # noqa: F401  (保持与 C067 相同的依赖面)

_TILE_NAMES = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
               "1b", "2b", "3b", "4b", "5b", "6b", "7b", "8b", "9b",
               "1t", "2t", "3t", "4t", "5t", "6t", "7t", "8t", "9t",
               "东", "南", "西", "北", "中", "发", "白"]


def ukeire_live(rem, vis_vec=None):
    """neigh 张数与「公开信息口径」的真实剩余张数。vis_vec 为 34 维计数或 None。"""
    neigh = set(rem)
    for t in set(rem):
        if is_suit_tile(id_of(t)):
            suit, num = suit_and_num(id_of(t))
            for dd in (-2, -1, 1, 2):
                n = num + dd
                if 1 <= n <= 9:
                    neigh.add("%d%s" % (n, "wbt"[suit]))
    neigh.add("白")
    live = 0
    for t in neigh:
        seen = rem.count(t)
        if vis_vec is not None:
            seen += int(vis_vec[id_of(t)])
        live += max(0, 4 - min(4, seen))
    return float(len(neigh)), float(live)


def after_feat_v2(hand, d, e, g, vis_vec=None):
    """43 维：34 计数 + [副露, 杠, 向听, 5.0, 对数, 白数, 等待数] + [neigh, live]。"""
    rem = list(hand)
    rem.remove(d)
    from collections import Counter

    from mahjong.shanten import waits
    from mahjong.shanten_exact import shanten as S

    c = Counter(rem)
    pairs = sum(v // 2 for k, v in c.items() if k != "白")
    try:
        sh = S(rem, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
        w = len(waits(rem, exposed_melds=e, gangs=g)) if sh == 0 else 0
    except Exception:
        sh = 4
        w = 0
    base = [c.get(t, 0) / 4.0 for t in _TILE_NAMES]
    base += [float(e), float(g), float(sh), 5.0, float(pairs),
             float(c.get("白", 0)), float(w)]
    base.extend(ukeire_live(rem, vis_vec))
    import numpy as np
    return np.asarray(base, "float32")


def visible_vector(river, all_melds, meld_tiles=None):
    """公开可见牌 34 维计数：弃牌河 + 四家副露（含被碰/吃走的牌）。"""
    import numpy as np
    v = np.zeros(34, "float32")
    for t in (river or []):
        try:
            v[id_of(t)] += 1.0
        except Exception:
            pass
    for seat_melds in (all_melds or []):
        for m in (seat_melds or []):
            ts = meld_tiles(m) if meld_tiles else (m.get("tiles") if isinstance(m, dict) else m)
            for t in (ts or []):
                try:
                    v[id_of(t)] += 1.0
                except Exception:
                    pass
    return v
