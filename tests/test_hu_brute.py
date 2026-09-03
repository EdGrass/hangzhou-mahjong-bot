"""对拍测试：mahjong.hu 的 DP 实现 vs 朴素暴力枚举（随机手牌）。

暴力法（参考实现，仅作验证用途）：
- 无财神：直接递归 去掉一对 → 去掉面子（顺/刻）判空；
- 有财神（J<=2）：把财神逐一具体化为 33 种实体牌的全部组合，套无财神判定；
  七对同理（财神补对 = 具体化为某实体牌单张）。
用固定种子保证可复现。
"""
import itertools
import random
import unittest

from mahjong.hu import is_win
from mahjong.tiles import GOD_TILE, from_counts, is_suit_tile, tile_of


def _real_win_no_joker(counts):
    """无财神普通胡：枚举将 + 递归面子。counts: 33 维。"""
    if sum(counts) == 0:
        return True
    # 找将：允许在递归任意层先拿一对（等价枚举）——用先将后面子即可
    return _can_melds_all(counts, [p for p in range(33) if counts[p] >= 2])


def _can_melds(counts):
    if sum(counts) == 0:
        return True
    i = next((k for k in range(33) if counts[k] > 0), None)
    if i is None:
        return True
    # 刻子
    if counts[i] >= 3:
        c = counts.copy(); c[i] -= 3
        if _can_melds(c):
            return True
    # 顺子（数牌且可作头）
    if is_suit_tile(i):
        n = i % 9
        if n <= 6:
            for j in (i + 1, i + 2):
                if counts[j] < 1:
                    break
            else:
                c = counts.copy(); c[i] -= 1; c[i + 1] -= 1; c[i + 2] -= 1
                if _can_melds(c):
                    return True
    return False


def _can_melds_all(counts, pair_candidates):
    for p in pair_candidates:
        c = counts.copy(); c[p] -= 2
        if _can_melds(c):
            return True
    return False


def _qidui_no_joker(counts):
    return all(v % 2 == 0 for v in counts)


def brute_win(tiles14):
    """暴力参考：返回 (普通胡, 七对) 布尔对。tiles14 含白板=财神。"""
    from mahjong.tiles import id_of
    counts = [0] * 33
    jokers = 0
    for t in tiles14:
        if t == GOD_TILE:
            jokers += 1
        else:
            counts[id_of(t)] += 1

    real = from_counts(counts)
    # 财神具体化（≤2 个时 33^J 枚举；更多则跳过该手）
    if jokers > 2:
        return None
    std = False
    qidui = False
    for roles in itertools.product(range(33), repeat=jokers):
        c = counts.copy()
        for r in roles:
            c[r] += 1
        std = std or _can_melds_all(c, [p for p in range(33) if c[p] >= 2])
        qidui = qidui or _qidui_no_joker(c)
    return std, qidui


def _random_hand(rng, max_jokers=2):
    tiles = []
    pool = [tile_of(i) for i in range(33)]
    for _ in range(14):
        if rng.random() < 0.12 and max_jokers:
            tiles.append(GOD_TILE)
        else:
            tiles.append(rng.choice(pool))
    return tiles


class TestBruteForceCross(unittest.TestCase):
    def test_cross_500_random_hands(self):
        rng = random.Random(20260903)
        mismatch = []
        for k in range(500):
            hand = _random_hand(rng)
            jokers = hand.count(GOD_TILE)
            if jokers > 2:
                continue            # 暴力法枚举上限
            b = brute_win(hand)
            if b is None:
                continue
            std_b, qidui_b = b
            expect = std_b or qidui_b
            got = is_win(hand)
            if got != expect:
                mismatch.append((hand, expect, got, std_b, qidui_b))
                if len(mismatch) >= 5:
                    break
        self.assertEqual(mismatch, [], "对拍不一致: %r" % (mismatch[:3],))

    def test_cross_no_joker_specific(self):
        # 无财神手牌专项对拍（随机）
        rng = random.Random(7)
        pool = [tile_of(i) for i in range(33)]
        for _ in range(300):
            hand = [rng.choice(pool) for _ in range(14)]
            b = brute_win(hand)
            self.assertEqual(is_win(hand), b[0] or b[1], hand)


if __name__ == "__main__":
    unittest.main()
