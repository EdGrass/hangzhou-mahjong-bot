# -*- coding: utf-8 -*-
"""shanten 分解去重优化的回归护栏。

优化：`_decompositions_uncached` 每层只保留 unique `(m,p,t)`。
正确性由 35,700 语料 + 全量测试保证；这里只锁住“缓存里确实是 unique tuple”这个性能性质，
防止未来误改回 list/append 造成指数级重复膨胀。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mahjong.shanten_exact as se  # noqa: E402
from mahjong.tiles import counts_of  # noqa: E402


class TestDecompositionDedup(unittest.TestCase):
    def setUp(self):
        self.old_cache = se._ITER_CACHE
        self.old_max = se._ITER_CACHE_MAX
        se._ITER_CACHE = {}
        se._ITER_CACHE_MAX = 200000

    def tearDown(self):
        se._ITER_CACHE = self.old_cache
        se._ITER_CACHE_MAX = self.old_max

    def test_uncached_returns_unique_triples(self):
        cases = [
            ["1w", "1w", "2w", "2w", "3w", "3w", "4w", "4w", "5w", "5w", "6w", "6w", "7w", "白"],
            ["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "白", "东"],
            ["1t", "1t", "1t", "2t", "2t", "3t", "3t", "4t", "4t", "5t", "5t", "白", "白", "中"],
        ]
        for hand in cases:
            dec = se._decompositions_uncached(list(counts_of(hand)), True)
            self.assertIsInstance(dec, tuple)
            self.assertEqual(len(dec), len(set(dec)),
                             "分解列表必须无重复三元组：%s" % hand)
            for item in dec:
                self.assertEqual(len(item), 3)

    def test_cache_values_are_unique_tuples(self):
        hand = ["1w", "1w", "2w", "2w", "3w", "3w", "4w", "4w", "5w", "5w", "6w", "6w", "7w", "白"]
        se._decompositions(list(counts_of(hand)), True)
        self.assertTrue(se._ITER_CACHE, "应写入分解缓存")
        for key, val in se._ITER_CACHE.items():
            self.assertIsInstance(val, tuple, key)
            self.assertEqual(len(val), len(set(val)), "缓存值必须去重：%s" % (key,))


if __name__ == "__main__":
    unittest.main()
