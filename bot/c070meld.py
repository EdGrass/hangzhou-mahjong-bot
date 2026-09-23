# -*- coding: utf-8 -*-
"""C070 副露决策共享特征/构造：把「这条吃/碰窗口该不该应」变成可训练的二选一排序。

结构（与 C067/C068 弃牌模型同型：相对基线优势）：
  基线 = 现有 C045 判据（want_claim_strict_meld：未听向听严格下降 / 已听等待变多）
  选项 = {应(summary claim), 过(pass)}；模型给两个选项打分，超过 margin 才改判。
每行特征 = 公共块 + 选项块：
  公共(96) = route_feats(应之前,22) + 手牌34 + offer onehot34 + 副露3 + 巡目1 + 河长1 + 可见张1
  选项(47) = is_claim(1) + kind onehot(2) + route_feats(应后,22) + route_delta(22)
定位：现有权重是「路线无关」的；本模型让网络看到「副露会毁掉哪条路线」
（七对/门牌/爆头/四白/清一色）以及「副露后最快听牌形」，再决定应还是过。
"""
from __future__ import annotations

import numpy as np

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as _shanten
from mahjong.tiles import counts_of, id_of

from .c069routes import route_feats
from .speed import _chi_pairs
from .speedt import _best_discard_t, _pref
from .speedtugc import want_claim_strict_meld

COMMON_DIM = 96
OPTION_DIM = 47
ROW_DIM = COMMON_DIM + OPTION_DIM


_TILES34 = None


def tiles_from_counts(c34):
    """34 维计数 → 牌码列表（末位白）。"""
    global _TILES34
    if _TILES34 is None:
        from mahjong.tiles import ID_TILES
        _TILES34 = [ID_TILES[j] for j in range(33)] + ["白"]
    out = []
    for j in range(34):
        k = int(round(float(c34[j])))
        if k > 0:
            out.extend([_TILES34[j]] * k)
    return out


def meld_list(meld_counts):
    """[碰,吃,杠] → 伪 view melds 列表（供生产判据函数使用）。"""
    peng, chi, gang = (int(round(float(x))) for x in meld_counts)
    out = []
    for _ in range(peng):
        out.append({"type": "peng", "tile": "", "tiles": []})
    for _ in range(chi):
        out.append({"type": "chi", "tile": "", "tiles": []})
    for _ in range(gang):
        out.append({"type": "gang", "tile": "", "tiles": []})
    return out


def synthetic_view(hand, meld_counts, offer, phase):
    return {"my_hand": list(hand), "offer_tile": offer, "melds": meld_list(meld_counts),
            "phase": phase, "god": {}, "river": [], "all_melds": []}


def rule_claim(view, kind, pair=None):
    """生产判据（C045）：未听向听严格下降 / 已听等待变多。"""
    try:
        return bool(want_claim_strict_meld(view, kind, pair))
    except Exception:
        return False


def best_after_claim(hand13, offer, kind, pair, e, g):
    """副露后（+1 面子）选最优弃牌，返回 (残牌13, 向听, 等待数, 弃牌)。"""
    h = list(hand13)
    if kind == "chi":
        if not pair:
            return None
        for t in pair:
            if t not in h:
                return None
            h.remove(t)
    else:
        for _ in range(2):
            if offer not in h:
                return None
            h.remove(offer)
    e2 = e + 1
    if len(h) != 14 - 3 * e2 - g:
        return None
    best = None
    for d in sorted(set(h)):
        rem = list(h); rem.remove(d)
        try:
            s = _shanten(rem, qidui=False, exposed_melds=e2, gangs=g)
            w = len(waits(rem, exposed_melds=e2, gangs=g)) if s == 0 else 0
        except Exception:
            continue
        key = (s, -w, _pref(d, h))
        if best is None or key < best[0]:
            best = (key, rem, s, w, d)
    if best is None:
        return None
    return best[1], best[2], best[3], best[4]


def common_block(hand, meld_counts, offer, draws, river_len, vis_offer, e, g):
    row = list(route_feats(hand, e, g))
    row += [0.0] * 34
    c = counts_of(list(hand))
    for i in range(34):
        row[len(route_feats(hand, e, g)) + i] = c[i] / 4.0
    row += [0.0] * 34
    row[22 + 34 + id_of(offer)] = 1.0
    row += [float(meld_counts[0]), float(meld_counts[1]), float(meld_counts[2])]
    row += [min(1.0, float(draws) / 12.0), min(1.0, float(river_len) / 24.0),
            max(0.0, 4.0 - float(vis_offer)) / 4.0]
    while len(row) < COMMON_DIM:
        row.append(0.0)
    return row[:COMMON_DIM]


def rows_for_window(hand, meld_counts, offer, kind, draws=0, river_len=0,
                    vis_offer=0, vis_vec=None, chi_pairs=None):
    """返回 (rows[2], base_idx, claim_possible)  —— rows[0]=应, rows[1]=过。"""
    e = int(meld_counts[0] + meld_counts[1] + meld_counts[2])
    g = int(meld_counts[2])
    common = common_block(hand, meld_counts, offer, draws, river_len, vis_offer, e, g)
    before = list(route_feats(hand, e, g))
    view = synthetic_view(hand, meld_counts, offer,
                          "response_peng" if kind == "peng" else "response_chi")
    # ---- 基线判据 ----
    if kind == "peng":
        cnt = list(hand).count(offer)
        pair = None
        base_claim = False
        if cnt >= 3 and rule_claim(view, "gang_ming"):
            base_claim = True
        elif cnt >= 2 and rule_claim(view, "peng"):
            base_claim = True
    else:
        pair = None
        base_claim = False
        pairs = chi_pairs if chi_pairs is not None else _chi_pairs(list(hand), offer)
        for p in pairs:
            if rule_claim(view, "chi", p):
                base_claim = True
                pair = p
                break
    # ---- 应选项状态 ----
    after = None
    if kind == "chi":
        bestkey = None
        for p in (chi_pairs if chi_pairs is not None else _chi_pairs(list(hand), offer)):
            got = best_after_claim(hand, offer, "chi", p, e, g)
            if got is None:
                continue
            rem, s, w, _d = got
            k = (s, -w)
            if bestkey is None or k < bestkey:
                bestkey = k
                after = route_feats(rem, e + 1, g)
    else:
        got = best_after_claim(hand, offer, "peng", None, e, g)
        if got is not None:
            rem, s, w, _d = got
            after = route_feats(rem, e + 1, g)
    claim_possible = after is not None
    if after is None:
        after = list(route_feats(hand, e, g))
    claim_block = [1.0, 1.0 if kind == "chi" else 0.0,
                   0.0 if kind == "chi" else 1.0] + list(after) + \
        [a - b for a, b in zip(after, before)]
    pass_block = [0.0, 0.0, 0.0] + before + [0.0] * len(before)
    rows = [common + claim_block, common + pass_block]
    return rows, (0 if base_claim else 1), claim_possible
