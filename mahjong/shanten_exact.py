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


def _decompositions_uncached(c, god_face=True):
    """34 维计数（末位=白）。产出 (m, p, t)。白作为万能补位参与块。

    god_face=False（C013 白保留模式，2026-09-09）：白不得补足面子
    （顺/刻/纯白面），仅可做对子/塔子伴侣/孤张——用于评估"白留作万能
    听"的弃牌路径（向听保守化），爆头态导向。
    """
    out = set()
    i = _anchor_first(c)
    if i < 0:
        out.add((0, 0, 0))
        return tuple(out)
    j = c[_GOD]
    cc = list(c)
    if i == _GOD:  # 只剩白板
        if j >= 3 and god_face:
            c3 = cc[:]
            c3[_GOD] -= 3
            for m, p, t in _decompositions(c3, god_face):
                out.add((m + 1, p, t))
        if j >= 2:
            c2 = cc[:]
            c2[_GOD] -= 2
            for m, p, t in _decompositions(c2, god_face):
                out.add((m, p + 1, t))
        c1 = cc[:]
        c1[_GOD] = 0
        for m, p, t in _decompositions(c1, god_face):
            out.add((m, p, t))
        return tuple(out)
    # 刻子：实体 3 / 实体 2+1白 / 实体 1+2白
    if cc[i] >= 3:
        c3 = cc[:]
        c3[i] -= 3
        for m, p, t in _decompositions(c3, god_face):
            out.add((m + 1, p, t))
    if cc[i] >= 2 and j >= 1 and god_face:
        c2 = cc[:]
        c2[i] -= 2
        c2[_GOD] -= 1
        for m, p, t in _decompositions(c2, god_face):
            out.add((m + 1, p, t))
    if cc[i] >= 1 and j >= 2 and god_face:
        c1 = cc[:]
        c1[i] -= 1
        c1[_GOD] -= 2
        for m, p, t in _decompositions(c1, god_face):
            out.add((m + 1, p, t))
    # 顺子：实体位置 1~3 张，白补其余（仅数牌）
    if i < _NUM:
        base = (i // 9) * 9
        n = i % 9
        if n <= 6:
            for mask in (0b111, 0b110, 0b101, 0b011, 0b100, 0b010, 0b001):
                need_w = 3 - bin(mask).count("1")
                if need_w > j or (need_w and not god_face):
                    continue
                ks = [i + k for k in range(3) if (mask >> (2 - k)) & 1]
                if all(cc[k] > 0 for k in ks):
                    c3 = cc[:]
                    for k in ks:
                        c3[k] -= 1
                    if need_w:
                        c3[_GOD] -= need_w
                    for m, p, t in _decompositions(c3, god_face):
                        out.add((m + 1, p, t))
        # 塔子：实体两连(差1/差2)；实体1+1白 万能塔（god_face=False 时禁——
        # 白不得被塔子绑定，只能成对/孤，保证成型后白自然为孤（爆头导向））
        for d in (1, 2):
            k2 = i + d
            if k2 < base + 9 and cc[k2] > 0:
                c2 = cc[:]
                c2[i] -= 1
                c2[k2] -= 1
                for m, p, t in _decompositions(c2, god_face):
                    out.add((m, p, t + 1))
        if j >= 1 and god_face:
            cw = cc[:]
            cw[i] -= 1
            cw[_GOD] -= 1
            for m, p, t in _decompositions(cw, god_face):
                out.add((m, p, t + 1))
    # 对子：实体2 / 实体1+1白（纯白对/纯白面在实体耗尽后于 _GOD 锚统一处理）
    if cc[i] >= 2:
        c2 = cc[:]
        c2[i] -= 2
        for m, p, t in _decompositions(c2, god_face):
            out.add((m, p + 1, t))
    if j >= 1:
        cw = cc[:]
        cw[i] -= 1
        cw[_GOD] -= 1
        for m, p, t in _decompositions(cw, god_face):
            out.add((m, p + 1, t))
    # 孤张：整位当孤（含实体余张）
    c1 = cc[:]
    c1[i] = 0
    for m, p, t in _decompositions(c1, god_face):
        out.add((m, p, t))
    return tuple(out)


_ITER_CACHE = {}
_ITER_CACHE_MAX = 200000


def _decompositions(c, god_face=True):
    """`_decompositions_uncached` 的**记忆化**版本：key=(counts 元组, god_face)。

    为什么需要（2026-09-16 实测）：原实现是**无缓存的递归枚举生成器**，同一子计数向量
    被反复枚举 ⇒ 某些形状退化成指数级（`exact_shanten` 单次 p95=618ms、max=1.9s；
    我方基线决策 p95=92ms、max=300ms 也主要来自这里）。这直接**封死了任何需要多次
    调用精确向听的候选**（真实进张候选 c135 因此 p95=5.7s 被延迟门禁淘汰）。
    缓存后同一向量只枚举一次；并且每层只保留去重后的 `(m,p,t)`，因为向听只依赖三元组集合。

    正确性：同一计数向量的分解集合是纯函数 ⇒ 缓存安全（265 项单测含引擎黄金集）。
    内存：超过 `_ITER_CACHE_MAX` 条整体清空（宁偶尔重算，不无限增长）。
    """
    key=(tuple(c), bool(god_face))
    hit=_ITER_CACHE.get(key)
    if hit is not None:
        return hit
    val=_decompositions_uncached(list(c), god_face)
    if len(_ITER_CACHE)>=_ITER_CACHE_MAX:
        _ITER_CACHE.clear()
    _ITER_CACHE[key]=val
    return val


def _iter_decompositions(c, god_face=True):
    """兼容旧调用点（生成器接口）。"""
    for item in _decompositions(c, god_face):
        yield item

def _score(m, p, t, base_faces=4):
    if m > base_faces:
        return 99
    need = base_faces - m
    has = 1 if p >= 1 else 0
    ta = t + max(0, p - 1)
    return max(0, 2 * need - has - min(ta, need))


@lru_cache(maxsize=131072)
def _shanten_counts(counts_tuple, exposed, gangs, god_face):
    """分解枚举取最小 `_score`。

    2026-09-17 提速（**结果逐位不变**，35,700 条冻结语料对拍 0 差异）：
      · `_score` 内联 —— cProfile 显示 `_score` 自身 + 其内置 `max/min`
        在真机决策里占 ~38% 墙钟（53.6M 次调用 / 97s）；
      · 去掉 `_iter_decompositions` 生成器层，直接查 `_ITER_CACHE`。
    `_score` / `_iter_decompositions` 仍保留导出（兼容旧调用点与单测）。
    """
    base = 4 - exposed
    best = 2 * base
    key = (counts_tuple, bool(god_face))
    dec = _ITER_CACHE.get(key)
    if dec is None:
        dec = _decompositions_uncached(list(counts_tuple), god_face)
        if len(_ITER_CACHE) >= _ITER_CACHE_MAX:
            _ITER_CACHE.clear()
        _ITER_CACHE[key] = dec
    for m, p, t in dec:
        if m > base:
            continue                      # 等价于 _score 的 `return 99`
        need = base - m
        has = 1 if p >= 1 else 0
        _pm = p - 1
        ta = t + (_pm if _pm > 0 else 0)  # = t + max(0, p-1)
        _mn = ta if ta < need else need   # = min(ta, need)
        v = 2 * need - has - _mn
        if v < 0:
            v = 0                         # = max(0, ...)
        if v < best:
            best = v
            if best == 0:
                break
    return best


def _qidui_shanten(counts):
    """七对向听：实体对数 + 白补孤 + 余白两两成对（仅无副露/无杠可用）。"""
    j = counts[_GOD]
    pairs = sum(v // 2 for v in counts[:_GOD])
    odds = sum(1 for v in counts[:_GOD] if v % 2 == 1)
    paired = min(odds, j)
    pairs += paired
    pairs += (j - paired) // 2
    return max(0, 6 - pairs)


def shanten(hand, qidui=True, exposed_melds=0, gangs=0, god_meld=True):
    """摸牌前暗牌（13-3e-g 张，含财神）的精确向听数。

    一般形基准面子 = 4-e；七对仅当 e=g=0 时参与。
    god_meld=False（C013 白保留评估模式）：白不补面子（仅对/塔/孤），
    评估"留白万能听"路径的保守向听。
    """
    e = int(exposed_melds or 0)
    g = int(gangs or 0)
    need_len = 13 - 3 * e - g
    if len(hand) != need_len:
        raise ValueError("副露 %d 杠 %d 时向听判定需 %d 张，实际 %d" % (
            e, g, need_len, len(hand)))
    counts = list(counts_of(hand))
    best = _shanten_counts(tuple(counts), e, g, bool(god_meld))
    if qidui and e == 0 and g == 0:
        q = _qidui_shanten(counts)
        if q < best:
            best = q
    return best
