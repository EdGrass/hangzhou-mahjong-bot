# -*- coding: utf-8 -*-
"""meld_offer_audit 单测：向听计算要能吃 13/14 张两种开局形态（修过一个"全是 0 统计"的 bug）。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("moa", os.path.join(ROOT, "tools", "meld_offer_audit.py"))
moa = importlib.util.module_from_spec(spec)
sys.modules["moa"] = moa
spec.loader.exec_module(moa)


class TestShantenTolerant(unittest.TestCase):
    def test_13_tile_hand_computes(self):
        h = ["1w", "2w", "3w", "5w", "7w", "9w", "3t", "4t", "6t", "8b", "东", "南", "西"]
        self.assertIsNotNone(moa.sh(h, 0, 0))

    def test_14_tile_hand_does_not_return_none(self):
        """★ 回归：复盘 start_hands 有时是 14 张；旧实现会让 whole 统计全为 0。"""
        h13 = ["1w", "2w", "3w", "5w", "7w", "9w", "3t", "4t", "6t", "8b", "东", "南", "西"]
        h14 = h13 + ["9t"]
        v14 = moa.sh(h14, 0, 0)
        self.assertIsNotNone(v14)
        # 14 张的口径 = "逐张试打后的最小向听" ⇒ 不可能比原始 13 张更差
        self.assertLessEqual(v14, moa.sh(h13, 0, 0))


class TestValueOfTake(unittest.TestCase):
    def test_peng_needs_two_tiles(self):
        self.assertEqual(moa.value_of_take(["1w", "2w"], "1w", "peng", 0, 0), (None, 0))

    def test_peng_returns_value_when_pair_present(self):
        h = ["1w", "1w", "3w", "4w", "5w", "6w", "7w", "9w", "9t", "东", "南", "西", "白", "9b"]
        v, n = moa.value_of_take(h, "1w", "peng", 0, 0)
        self.assertIsNotNone(v)
        self.assertEqual(n, 2)

    def test_chi_finds_a_sequence(self):
        h = ["1w", "2w", "5w", "5w", "6w", "7w", "9w", "9t", "东", "南", "西", "白", "9b", "8b"]
        v, n = moa.value_of_take(h, "3w", "chi", 0, 0)
        self.assertIsNotNone(v)
        self.assertEqual(n, 2)


class TestShantenCache(unittest.TestCase):
    """缓存必须与直算一致（否则所有基于 sh() 的统计都会偏）。"""

    def test_cache_matches_direct(self):
        from mahjong.shanten_exact import shanten as ex
        h = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南"]
        self.assertEqual(moa.sh(h, 0, 0), ex(list(h), qidui=True, exposed_melds=0, gangs=0))
        # 第二次调用走缓存，结果必须一样
        self.assertEqual(moa.sh(h, 0, 0), ex(list(h), qidui=True, exposed_melds=0, gangs=0))

    def test_cache_key_includes_melds(self):
        """同一批牌在不同副露数下长度要求不同 ⇒ 缓存 key 必须含 ex/gg，否则会串味。
        ex=0 要 13 张；ex=1 要 10 张。"""
        h13 = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南"]
        h10 = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t"]
        v0 = moa.sh(h13, 0, 0)
        v1 = moa.sh(h10, 1, 0)
        self.assertIsNotNone(v0)
        self.assertIsNotNone(v1)
        # 再取一次（走缓存）结果必须稳定
        self.assertEqual(moa.sh(h13, 0, 0), v0)
        self.assertEqual(moa.sh(h10, 1, 0), v1)


class TestUkeire(unittest.TestCase):
    def test_ukeire_positive_and_sane(self):
        h = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南"]
        u = moa.ukeire(h, 0, 0)
        self.assertIsNotNone(u)
        self.assertGreater(u, 0)
        self.assertLessEqual(u, 136)

    def test_ukeire_tolerates_14_tiles(self):
        h13 = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南"]
        u13 = moa.ukeire(h13, 0, 0)
        u14 = moa.ukeire(h13 + ["9b"], 0, 0)
        self.assertIsNotNone(u14)
        self.assertGreaterEqual(u14, u13)     # 多一张牌不可能让进张变少（可以先打掉它）


if __name__ == "__main__":
    unittest.main()
