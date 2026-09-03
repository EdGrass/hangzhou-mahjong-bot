"""mahjong/shanten_exact —— 精确向听数（S1：真·速度基线地基）。

定义：向听数 k ⇔ 恰需 k 次「摸 1 张任意牌 + 打 1 张」可达听牌（0 = 已听牌）。

实现：完全拆解。每张暗牌消费为四类块之一：
  面子 m（顺/刻，3 张）；对子 p（对子块数）；塔子 t（2 张同花差 1/差 2 两连）；
  孤张（不计块）。
对每个拆解 (m, p, t) 估向听：
    need = 4 - m                     （还需的面子数）
    has  = 1 若 p >= 1（有现成将）
    ta   = t + max(0, p - 1)         （多余对子可作刻子胚 = 塔子）
    shanten = max(0, 2*need - has - min(ta, need))
取全拆解最小值。验证：shanten==0 与引擎 tenpai 一致；shanten<=1 与引擎
one-swap 判定抽样对拍；已知手牌用例锁定。

注：本版不含财神/副露（jokers/exposed/gangs 后续扩展，接口预留）。
"""
from __future__ import annotations

from functools import lru_cache

from .tiles import counts_of

_NUM = 27  # 33 实体中的前 27 = 数牌


def _anchor_first(counts):
    for i, c in enumerate(counts):
        if c:
            return i
    return -1


def _iter_decompositions(counts):
    """从 anchor 位按（面子/塔子/对子/孤张）消费，产出 (m, p, t)。"""
    i = _anchor_first(counts)
    if i < 0:
        yield (0, 0, 0)
        return
    c = list(counts)
    # 刻子
    if c[i] >= 3:
        cc = c[:]
        cc[i] -= 3
        for m, p, t in _iter_decompositions(cc):
            yield (m + 1, p, t)
    # 顺子 / 塔子（数牌）
    if i < _NUM:
        base = (i // 9) * 9
        n = i % 9
        if n <= 6 and c[i + 1] and c[i + 2]:
            cc = c[:]
            cc[i] -= 1
            cc[i + 1] -= 1
            cc[i + 2] -= 1
            for m, p, t in _iter_decompositions(cc):
                yield (m + 1, p, t)
        for d in (1, 2):
            j = i + d
            if j >= base + 9 or c[j] == 0:
                continue
            cc = c[:]
            cc[i] -= 1
            cc[j] -= 1
            for m, p, t in _iter_decompositions(cc):
                yield (m, p, t + 1)
    # 对子
    if c[i] >= 2:
        cc = c[:]
        cc[i] -= 2
        for m, p, t in _iter_decompositions(cc):
            yield (m, p + 1, t)
    # 孤张：整位当孤（对/刻分支已覆盖复用，此处处理余张）
    cc = c[:]
    cc[i] = 0
    for m, p, t in _iter_decompositions(cc):
        yield (m, p, t)


def _score(m, p, t):
    if m > 4:
        return 99
    need = 4 - m
    has = 1 if p >= 1 else 0
    ta = t + max(0, p - 1)
    return max(0, 2 * need - has - min(ta, need))


@lru_cache(maxsize=65536)
def _shanten_counts(counts_tuple):
    best = 8
    for m, p, t in _iter_decompositions(list(counts_tuple)):
        s = _score(m, p, t)
        if s < best:
            best = s
            if best == 0:
                break
    return best


def shanten(hand13):
    """13 张暗牌（本版：无财神/无副露）的精确向听数。"""
    if len(hand13) != 13:
        raise ValueError("向听数需要 13 张，实际 %d" % len(hand13))
    counts = list(counts_of(hand13))
    if counts[33]:
        raise NotImplementedError("财神向听为后续版本（本版仅实体牌）")
    return _shanten_counts(tuple(counts[:33]))
