# -*- coding: utf-8 -*-
"""discard_regret 单测：把「最优弃牌」与「遗憾分类」的语义钉死。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("dr", os.path.join(ROOT, "tools", "discard_regret.py"))
dr = importlib.util.module_from_spec(spec)
sys.modules["dr"] = dr
spec.loader.exec_module(dr)


class TestBestDiscards(unittest.TestCase):
    def test_returns_a_best_pair(self):
        hand = ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "9w", "9w", "9w"]
        bs, bw, table = dr.best_discards(hand, 0, 0)
        self.assertIsNotNone(bs)
        self.assertGreaterEqual(bw, 0)
        self.assertTrue(table)
        # 表里每一张可打的牌都要有价值对
        for t, (sh, w) in table.items():
            self.assertGreaterEqual(sh, 0)
        self.assertEqual(min(v[0] for v in table.values()), bs)

    def test_first_turn_hand_from_real_corpus_shape(self):
        # 一个真实形态的 14 张起手（孤张字牌多条）
        hand = ["1w", "2w", "3w", "5w", "7w", "9w", "3t", "4t", "6t", "8b", "东", "南", "西", "白"]
        bs, bw, table = dr.best_discards(hand, 0, 0)
        self.assertIn(min(v[0] for v in table.values()), (bs,))
        self.assertLessEqual(bs, 4)


class TestClassify(unittest.TestCase):
    def test_none_when_equal(self):
        self.assertEqual(dr.classify((1, 8), (1, 8)), "none")

    def test_none_when_wider_than_best(self):
        self.assertEqual(dr.classify((1, 9), (1, 8)), "none")

    def test_narrower_when_same_shanten_but_fewer_waits(self):
        self.assertEqual(dr.classify((1, 4), (1, 8)), "narrower")

    def test_shanten_one_worse(self):
        self.assertEqual(dr.classify((2, 0), (1, 8)), "shanten+1")

    def test_unknown_on_missing(self):
        self.assertEqual(dr.classify(None, (1, 8)), "unknown")
        self.assertEqual(dr.classify((1, 8), None), "unknown")


if __name__ == "__main__":
    unittest.main()
