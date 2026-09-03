"""mahjong/shanten_exact —— 精确向听数（S1：真·速度基线地基，含财神）。

定义：向听数 k ⇔ 恰需 k 次「摸 1 张任意牌 + 打 1 张」可达听牌（0 = 已听牌）。

实现：完全拆解。每张牌消费为四类块之一：
  面子 m（顺/刻，3 张；含白板万能补位：实体 1~3 + 白补足，3 白亦可成面）；
  对子 p（实体 2 / 实体 1 + 白 1 / 白 2）；
  塔子 t（同花差 1/差 2 两连；实体 1 + 白 1 万能塔；字牌不能成顺塔）；
  孤张（含孤白，不计块）。
对每个拆解 (m, p, t) 估向听：
    need = 4 - m
    has  = 1 若 p >= 1
    ta   = t + max(0, p - 1)
    shanten = max(0, 2*need - has - min(ta, need))
取全拆解最小值；七对分支（无副露时）= max(0, 6 - 实体对数 - 白可补对数上限)。
验证：向听==0 与引擎 tenpai（含财神 waits）一致；≤1 与一换判定抽样对拍。

接口：shanten(hand13[, qidui=True]) —— 13 张暗牌（含白；副露折算后续扩展）。
"""
from __future__ import annotations

from functools import lru_cache

from .tiles import counts_of

_NUM = 27        # 33 实体前 27 = 数牌
_GOD = 33        # 白板在 34 维计数中的位置


def _anchor_first(counts):
    for i, c in enumerate(counts):
        if c:
            return i
    return -1


def _face_ok(kind_ids, c):
    return all(c[k] > 0 for k in kind_ids)


def _iter_decompositions(c):
    """34 维计数（末位=白）。产出 (m, p, t)。白作为万能补位参与块。"""
    i = _anchor_first(c)
    if i < 0:
        yield (0, 0, 0)
        return
    j = c[_GOD]
    cc = list(c)
    if i == _GOD:  # 只剩白板
        if j >= 3:
            c3 = cc[:]
            c3[_GOD] -= 3
            for m, p, t in _iter_decompositions(c3):
                yield (m + 1, p, t)
        if j >= 2:
            c2 = cc[:]
            c2[_GOD] -= 2
            for m, p, t in _iter_decompositions(c2):
                yield (m, p + 1, t)
        c1 = cc[:]
        c1[_GOD] = 0
        for m, p, t in _iter_decompositions(c1):
            yield (m, p, t)
        return
    # 刻子：实体 3 / 实体 2+1白 / 实体 1+2白
    if cc[i] >= 3:
        c3 = cc[:]
        c3[i] -= 3
        for m, p, t in _iter_decompositions(c3):
            yield (m + 1, p, t)
    if cc[i] >= 2 and j >= 1:
        c2 = cc[:]
        c2[i] -= 2
        c2[_GOD] -= 1
        for m, p, t in _iter_decompositions(c2):
            yield (m + 1, p, t)
    if cc[i] >= 1 and j >= 2:
        c1 = cc[:]
        c1[i] -= 1
        c1[_GOD] -= 2
        for m, p, t in _iter_decompositions(c1):
            yield (m + 1, p, t)
    # 顺子：实体位置 1~3 张，白补其余（仅数牌）
    if i < _NUM:
        base = (i // 9) * 9
        n = i % 9
        if n <= 6:
            for mask in (0b111, 0b110, 0b101, 0b011, 0b100, 0b010, 0b001):
                need_w = 3 - bin(mask).count("1")
                if need_w > j:
                    continue
                ks = [i + k for k in range(3) if (mask >> (2 - k)) & 1]
                if all(cc[k] > 0 for k in ks):
                    c3 = cc[:]
                    for k in ks:
                        c3[k] -= 1
                    if need_w:
                        c3[_GOD] -= need_w
                    for m, p, t in _iter_decompositions(c3):
                        yield (m + 1, p, t)
        # 塔子：实体两连(差1/差2)；实体1+1白 万能塔
        for d in (1, 2):
            k2 = i + d
            if k2 < base + 9 and cc[k2] > 0:
                c2 = cc[:]
                c2[i] -= 1
                c2[k2] -= 1
                for m, p, t in _iter_decompositions(c2):
                    yield (m, p, t + 1)
        if j >= 1:
            cw = cc[:]
            cw[i] -= 1
            cw[_GOD] -= 1
            for m, p, t in _iter_decompositions(cw):
                yield (m, p, t + 1)
    # 对子：实体2 / 实体1+1白（纯白对/纯白面在实体耗尽后于 _GOD 锚统一处理）
    if cc[i] >= 2:
        c2 = cc[:]
        c2[i] -= 2
        for m, p, t in _iter_decompositions(c2):
            yield (m, p + 1, t)
    if j >= 1:
        cw = cc[:]
        cw[i] -= 1
        cw[_GOD] -= 1
        for m, p, t in _iter_decompositions(cw):
            yield (m, p + 1, t)
    # 孤张：整位当孤（含实体余张）
    c1 = cc[:]
    c1[i] = 0
    for m, p, t in _iter_decompositions(c1):
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


def _qidui_shanten(counts):
    """七对向听：实体对数 + 白补对上限（白 1 张补 1 孤；白两两成对）。"""
    j = counts[_GOD]
    pairs = sum(v // 2 for v in counts[:_GOD])
    odds = sum(1 for v in counts[:_GOD] if v % 2 == 1)
    # 单张实体与白配对(≤min(odds, j))，剩余白两两成对
    paired = min(odds, j)
    pairs += paired
    pairs += (j - paired) // 2
    return max(0, 6 - pairs)


def shanten(hand13, qidui=True):
    """13 张暗牌（含财神白板）的精确向听数（一般形与七对取小）。"""
    if len(hand13) != 13:
        raise ValueError("向听数需要 13 张，实际 %d" % len(hand13))
    counts = list(counts_of(hand13))
    best = _shanten_counts(tuple(counts))
    if qidui:
        q = _qidui_shanten(counts)
        if q < best:
            best = q
    return best
