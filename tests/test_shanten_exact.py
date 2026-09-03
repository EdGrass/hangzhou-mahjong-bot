"""mahjong/shanten_exact 精确向听数测试（无财神版）。

验证：
1) 已知手牌锁定值（含七对分支、一般形极限）；
2) shanten==0 ⇔ 引擎 tenpai（随机抽样 100）；
3) shanten<=1 与「一换听牌」精确判定抽样对拍（12 手）。
"""
import random
import unittest

from mahjong.shanten import is_tenpai, waits
from mahjong.shanten_exact import _shanten_counts, shanten

W = "白"


def _qidui_shanten(hand13):
    from mahjong.tiles import counts_of
    c = counts_of(hand13)[:33]
    pairs = sum(v // 2 for v in c)
    return max(0, 6 - pairs)


def shanten_all(hand13):
    """一般形与七对取小（引擎判定七对语义：无副露）。"""
    return min(shanten(hand13), _qidui_shanten(hand13))


class TestKnownHands(unittest.TestCase):
    def test_max_shanten_all_singles(self):
        # 7 字 + 6 互不相邻数牌（无对无塔无面）→ 8
        h = ["东", "南", "西", "北", "中", "发", "1w", "4w", "7w",
             "1b", "4b", "1t", "7t"]
        self.assertEqual(shanten(h), 8)

    def test_four_melds_single_tenpai(self):
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "1b", "1b", "1b", "东"]
        self.assertEqual(shanten(h), 0)
        self.assertTrue(is_tenpai(h))

    def test_three_melds_pair_two_isolated(self):
        # 3 面子 + 将 + 2 不相邻孤 → 1 向听
        h = ["1b", "2b", "3b", "4b", "5b", "6b", "7t", "8t", "9t",
             "东", "东", "1w", "9w"]
        self.assertEqual(shanten(h), 1)

    def test_three_melds_pair_taatsu_tenpai(self):
        # 3 面子 + 将 + 两面塔 → 听牌
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "东", "东", "4t", "5t"]
        self.assertEqual(shanten(h), 0)
        self.assertTrue(is_tenpai(h))

    def test_two_melds_pair_taatsu_three_singles(self):
        # 2 面子 + 将 + 1 塔 + 3 不相干孤 → 2 向听
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "东", "东", "4t", "5t",
             "9b", "1b", "中"]
        self.assertEqual(shanten(h), 2)

    def test_qidui_six_pairs_single_tenpai(self):
        h = ["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t",
             "5t", "5t", "东", "东", "南"]
        self.assertEqual(shanten_all(h), 0)          # 七对分支
        self.assertTrue(is_tenpai(h))

    def test_qidui_five_pairs_three_singles(self):
        h = ["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t",
             "5t", "5t", "东", "南", "北"]
        self.assertEqual(shanten_all(h), 1)

    def test_honors_structure(self):
        h = ["东", "东", "东", "南", "南", "中", "中",
             "1w", "1w", "1w", "2b", "2b", "2b"]
        self.assertEqual(shanten(h), 0)


class TestConsistency(unittest.TestCase):
    pool = ["%d%s" % (i, s) for s in "wbt" for i in range(1, 10)] + \
           ["东", "南", "西", "北", "中", "发"]

    def _rand(self, rng):
        return [rng.choice(self.pool) for _ in range(13)]

    def test_zero_iff_tenpai(self):
        rng = random.Random(20260904)
        bad = []
        for _ in range(120):
            h = self._rand(rng)
            s = shanten_all(h)
            t = is_tenpai(h)
            if (s == 0) != t:
                bad.append((h, s, t))
                if len(bad) >= 3:
                    break
        self.assertEqual(bad, [], "向听=0 与 tenpai 不一致: %r" % bad[:2])

    def test_one_swap_consistency(self):
        """shanten<=1 ⇔ 存在「弃1摸1」后听牌（精确枚举，含七对）。"""
        from mahjong.shanten import waits as waits_exact
        rng = random.Random(7)
        checked = 0
        bad = []

        def one_swap(h13):
            for d in set(h13):
                rest = list(h13)
                rest.remove(d)
                for t in self.pool + [W]:
                    if rest.count(t) >= 4:
                        continue
                    if waits_exact(rest + [t]):
                        return True
            return False

        while checked < 10:
            h = self._rand(rng)
            if shanten_all(h) == 0:
                continue
            exp = 1 if one_swap(h) else 2
            got = 1 if shanten_all(h) == 1 else 2
            if exp != got:
                bad.append((h, got, exp))
                if len(bad) >= 3:
                    break
            checked += 1
        self.assertEqual(bad, [], "一换判定不一致: %r" % bad[:2])


if __name__ == "__main__":
    unittest.main()
