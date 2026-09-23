# -*- coding: utf-8 -*-
"""C069 目标牌型（route）特征：把「胡牌番型路线」显式量化成固定维向量。

动机：现有弃牌权重（`speedt._pref`：孤字 0/孤数 1/拆顺 2/拆对 3/白 4）与副露判据
（向听严格下降 / 听牌等待变多）都是**路线无关**的；但本游戏番值由分支倍率决定
（平胡 ×1、七对 ×2、豪华七对 2^(n+1)）× 4白 ×2 × 爆头 ×2 × 链 2^k（fan.py）。
因此「各种目标牌型下权重相同」本身就是错的结构。

本模块把每条路线的**进度**算出来（弃牌后 / 副露后均可调用），训练与在线共用：
  一般形：精确向听 / 听牌数 / 进张数
  七对：七对专用向听 / 对数 / 四张组数（豪华）/ 刻子数 / 单张数
  爆头：弃牌后是否已进入「摸任意张皆胡」状态（is_baotou）
  4 白：白牌数与凑四白进度
  清一色：最大花色集中度（数牌）
"""
from __future__ import annotations

import collections

from mahjong.hu import is_baotou
from mahjong.shanten import waits
from mahjong.shanten_exact import _qidui_shanten, shanten as _shanten
from mahjong.tiles import counts_of, id_of, is_suit_tile

ROUTE_DIM = 22
TILES34 = None

_NAMES = ["exposed", "gangs", "hand_len", "shanten", "tenpai", "waits", "ukeire",
          "qidui_shanten", "pairs", "quads", "triples", "singles", "whites",
          "four_white", "baotou", "suit_share", "honors", "branch_mult",
          "qidui_ok", "neigh_hi", "pair_pot", "meld_chi"]


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def ukeire_counts(hand):
    """邻接进张种数（含白）与张数（仅按手牌计）。"""
    neigh = set(hand)
    for t in set(hand):
        if is_suit_tile(id_of(t)):
            n, suit = int(t[0]), t[-1]
            for dd in (-2, -1, 1, 2):
                nn = n + dd
                if 1 <= nn <= 9:
                    neigh.add("%d%s" % (nn, suit))
    neigh.add("白")
    live = sum(max(0, 4 - hand.count(t)) for t in neigh)
    return float(len(neigh)), float(live)


def route_feats(hand, exposed=0, gangs=0):
    """返回长度 ROUTE_DIM 的 list[float]；hand = 摸牌前暗牌（13-3e-g 张）。"""
    e = int(exposed or 0)
    g = int(gangs or 0)
    c = collections.Counter(hand)
    counts = counts_of(list(hand))
    real = counts[:33]
    pairs = sum(1 for i in range(33) if real[i] >= 2)
    quads = sum(1 for i in range(33) if real[i] == 4)
    triples = sum(1 for i in range(33) if real[i] == 3)
    singles = sum(1 for i in range(33) if real[i] == 1)
    whites = counts[33]
    honors = sum(real[27:33])
    suit = [sum(real[0:9]), sum(real[9:18]), sum(real[18:27])]
    suit_share = (max(suit) / max(1, sum(suit))) if sum(suit) else 0.0

    sh = _safe(_shanten, list(hand), qidui=(e == 0 and g == 0),
               exposed_melds=e, gangs=g)
    wcnt = 0
    if sh == 0:
        w = _safe(waits, list(hand), exposed_melds=e, gangs=g)
        wcnt = len(w) if w else 0
    q_sh = None
    if e == 0 and g == 0:
        q_sh = _safe(_qidui_shanten, counts)
    neigh, live = ukeire_counts(list(hand))
    # 爆头 ⇒ 必然听牌（任意摸皆胡）；仅在听牌局面才调用昂贵判定
    baotou = 0.0
    if sh == 0 and _safe(is_baotou, list(hand), exposed_melds=e, gangs=g):
        baotou = 1.0
    branch_mult = 2.0 if (q_sh is not None and q_sh <= 1) else 1.0

    out = [
        float(e), float(g), len(hand) / 13.0,
        float(sh) if sh is not None else 8.0,
        1.0 if sh == 0 else 0.0,
        float(wcnt) / 34.0,
        float(neigh) / 40.0,
        float(q_sh) if q_sh is not None else 8.0,
        float(pairs) / 7.0,
        float(quads) / 4.0,
        float(triples) / 4.0,
        float(singles) / 13.0,
        float(whites) / 4.0,
        max(0.0, float(whites) - 2.0) / 2.0,
        baotou,
        float(suit_share),
        float(honors) / 13.0,
        branch_mult / 2.0,
        1.0 if q_sh is not None else 0.0,
        float(live) / 60.0,
        float(pairs + triples * 2 + quads * 3) / 12.0,
        1.0 if e > 0 else 0.0,
    ]
    assert len(out) == ROUTE_DIM, (len(out), ROUTE_DIM)
    return out
