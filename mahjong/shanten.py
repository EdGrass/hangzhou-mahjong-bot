"""听牌/等待牌与交换距离度量（mahjong 引擎，含财神）。

- waits(hand13)  → 摸到即可胡的等待牌列表；同种牌（含财神）已达 4 张不可摸，排除；
- is_tenpai      → 等待牌非空；
- min_swaps      → 与听牌的最小"弃一摸一"步数（0=已听牌；1=换 1 张可听；≥2 → 2）。
  注意：这是策略排序用度量（近似向听数），非标准向听数定义。

性能：is_win 结果按 14 张计数键做进程内记忆化；一换判定枚举 (弃牌 × 候选摸牌对)
并在数牌花色内只取"手牌已见 ±2"邻域 + 财神 作为候选，控制规模。
"""
from __future__ import annotations

from .hu import is_win
from .tiles import FULL_TILES, counts_of, id_of, is_suit_tile, suit_and_num

# 进程级 is_win 记忆（14 张排序计数键）
_win_memo = {}


def _win14(tiles, exposed=0, gangs=0):
    key = (tuple(sorted(tiles)), exposed, gangs)
    got = _win_memo.get(key)
    if got is None:
        got = is_win(tiles, exposed_melds=exposed, gangs=gangs)
        _win_memo[key] = got
    return got


def _waits_of(hand, exposed=0, gangs=0):
    """等待牌（内部：不查 deck，仅排除已 4 张）。"""
    counts = counts_of(hand)
    return [t for t in FULL_TILES
            if counts[id_of(t)] < 4 and _win14(hand + [t], exposed, gangs)]


def waits(hand, exposed_melds=0, gangs=0):
    """摸牌前暗牌（13-3e-g 张）的等待牌（34 种含白；同种满 4 张排除）。"""
    e, g = int(exposed_melds or 0), int(gangs or 0)
    need = 13 - 3 * e - g
    if len(hand) != need:
        raise ValueError("副露 %d 杠 %d 时等待判定需 %d 张，实际 %d" % (
            e, g, need, len(hand)))
    return _waits_of(hand, e, g)


def is_tenpai(hand, exposed_melds=0, gangs=0):
    e, g = int(exposed_melds or 0), int(gangs or 0)
    need = 13 - 3 * e - g
    if len(hand) != need:
        raise ValueError("副露 %d 杠 %d 时听牌判定需 %d 张，实际 %d" % (
            e, g, need, len(hand)))
    return bool(_waits_of(hand, e, g))


def _neighborhood(kinds):
    """候选摸牌集合：手牌已见牌面 + 其数牌邻域 ±2 + 财神。
    一换判定中，新摸牌只有落到"已有结构附近"或作财神补时才可能促成听牌，
    邻域外的新牌无法与 12 张残牌构成新面子/对子（保守近似，见模块 docstring）。"""
    cand = set(kinds) | {"白"}
    for k in kinds:
        if is_suit_tile(id_of(k)):
            s, n = suit_and_num(id_of(k))
            for delta in (-2, -1, 1, 2):
                m = n + delta
                if 1 <= m <= 9:
                    cand.add("%d%s" % (m, "wbt"[s]))
    return sorted(cand, key=id_of)


def _one_swap_to_tenpai(rest12):
    """弃 1 张后（rest12）是否存在摸 1 张使其听牌：
    ∃(t, u) 使 win(rest + t + u)。t=摸牌（促成听牌）、u=听牌后的和牌牌。"""
    base = set(rest12)
    cand = _neighborhood(base)
    n = len(cand)
    for i in range(n):
        t = cand[i]
        # 摸牌 t 需手牌该种 <4（物理可摸）；听牌后 u 无此约束
        if base_count(rest12, t) >= 4:
            continue
        for j in range(i, n):
            u = cand[j]
            if _win14(rest12 + [t, u]):
                return True
    return False


def base_count(tiles, tile):
    c = 0
    for t in tiles:
        if t == tile:
            c += 1
    return c


def min_swaps(hand13):
    """与听牌的最小交换步数（0/1/≥2→2）。"""
    if len(hand13) != 13:
        raise ValueError("需要 13 张，实际 %d" % len(hand13))
    if is_tenpai(hand13):
        return 0
    seen = set()
    for d in hand13:                        # 弃哪张
        if d in seen:
            continue
        seen.add(d)
        rest = list(hand13)
        rest.remove(d)
        if _one_swap_to_tenpai(rest):
            return 1
    return 2
