"""mahjong/shanten：听牌等待牌 + 交换距离度量（fixture 均已用引擎预验证）。"""
import unittest

from mahjong.shanten import is_tenpai, min_swaps, waits

ALL_REAL = ["%d%s" % (i, s) for s in "wbt" for i in range(1, 10)] + \
           ["东", "南", "西", "北", "中", "发"]


class TestWaits(unittest.TestCase):
    def test_single_wait_pair(self):
        # 123w456w789w 111b 单钓东（白可摸补对）
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "1b", "1b", "1b", "东"]
        self.assertEqual(sorted(waits(h)), ["东", "白"])

    def test_joker_single_wait_all34(self):
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "1b", "1b", "1b", "白"]
        self.assertEqual(len(waits(h)), 34)
        self.assertIn("白", waits(h))

    def test_multi_wait_with_extra_tiles(self):
        # 111w222w333w 45w 东东 → 引擎实测等待 {3w,6w,东,白}
        h = ["1w", "1w", "1w", "2w", "2w", "2w", "3w", "3w", "3w",
             "4w", "5w", "东", "东"]
        self.assertEqual(sorted(waits(h)), ["3w", "6w", "东", "白"])

    def test_not_tenpai(self):
        h = ["1w", "1w", "1w", "2w", "2w", "2w", "3w", "3w", "3w",
             "4w", "5w", "东", "南"]
        self.assertFalse(is_tenpai(h))
        self.assertEqual(waits(h), [])

    def test_white_full_excluded(self):
        # 3 顺 + 4 白：任意实体可摸即胡，但白已 4 张不可摸
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "白", "白", "白", "白"]
        w = waits(h)
        self.assertEqual(sorted(w), sorted(ALL_REAL))
        self.assertNotIn("白", w)


class TestMinSwaps(unittest.TestCase):
    def test_tenpai_zero(self):
        h = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
             "1b", "1b", "1b", "东"]
        self.assertEqual(min_swaps(h), 0)

    def test_one_swap(self):
        # 弃南摸东即可听（45w 双面 + 东东）
        h = ["1w", "1w", "1w", "2w", "2w", "2w", "3w", "3w", "3w",
             "4w", "5w", "东", "南"]
        self.assertEqual(min_swaps(h), 1)

    def test_scattered_capped(self):
        h = ["1w", "2w", "4w", "5w", "7w", "8w", "1b", "2b", "4b",
             "1t", "2t", "东", "南"]
        self.assertEqual(min_swaps(h), 2)     # ≥2 压缩为 2

    def test_bad_length(self):
        with self.assertRaises(ValueError):
            waits(["1w"] * 14)
        with self.assertRaises(ValueError):
            min_swaps(["1w"] * 12)

    def test_approx_vs_exact_random_hands(self):
        """邻域近似 vs 全 34² 精确参考（少量随机手，防近似漏判）。"""
        import random
        from mahjong.hu import is_win
        from mahjong.tiles import FULL_TILES

        rng = random.Random(20260903)
        pool = [t for t in FULL_TILES if t != "白"] * 4 + ["白"] * 4
        win_memo = {}

        def win14(tiles):
            key = tuple(sorted(tiles))
            if key not in win_memo:
                win_memo[key] = is_win(tiles)
            return win_memo[key]

        def exact_one_swap(h13):
            for d in set(h13):
                rest = list(h13)
                rest.remove(d)
                kinds = sorted(FULL_TILES, key=lambda t: t)
                for i, t in enumerate(kinds):
                    if rest.count(t) >= 4:
                        continue
                    for u in kinds[i:]:
                        if win14(rest + [t, u]):
                            return True
            return False

        checked = 0
        for _ in range(60):
            h = [rng.choice(pool) for _ in range(13)]
            if is_tenpai(h):
                continue                        # 0 值两侧一致，无需对比
            expect = 1 if exact_one_swap(h) else 2
            got = min_swaps(h)
            self.assertEqual(got, expect, "近似漏判: %s" % (h,))
            checked += 1
            if checked >= 4:
                break
        self.assertGreaterEqual(checked, 2)


if __name__ == "__main__":
    unittest.main()
