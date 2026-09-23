# -*- coding: utf-8 -*-
"""speedc151（路线加权出牌）单测：语义必须与设计一致，且不能破坏主键（向听）。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import (SpeedC151, _route_bonus, ROUTE_BONUS, _pick_discard_route,  # noqa: E402
                            _pair_count as moa_pair_count)
from bot.speedc135 import _best_discard_realukeire                                      # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten                               # noqa: E402


class TestPairPenalty(unittest.TestCase):
    """★ 方向护栏（2026-09-17 更正后）：语义是"**惩罚多对子**"，不是保对子。

    STATUS §4c-67：第 8 巡持对数 1~2 时听牌率最高，≥3 对暴跌到 13~30%；
    强玩家几乎不停在 ≥3 对 ⇒ 目标是把对数压回 ≤2。
    """

    def test_pair_count_helper(self):
        self.assertEqual(moa_pair_count(["1w", "1w", "2w", "2w", "3w"]), 2)
        self.assertEqual(moa_pair_count(["1w", "2w", "3w"]), 0)

    def test_bonus_when_pairs_drop_to_two_or_less(self):
        # 弃牌后剩 1 对 ⇒ 给加成（该弃）
        self.assertAlmostEqual(_route_bonus(["1w", "1w", "2w"], "3w"), ROUTE_BONUS)

    def test_no_bonus_when_still_many_pairs(self):
        # 弃牌后仍剩 3 对 ⇒ 不给加成
        self.assertAlmostEqual(_route_bonus(["1w", "1w", "2w", "2w", "3w", "3w"], "9b"), 0.0)

    def test_bonus_sign_is_positive_for_discard(self):
        import inspect
        src = inspect.getsource(_pick_discard_route)
        self.assertIn("u += _route_bonus", src, "多对子惩罚必须是**奖励弃牌**方向（u 增大）")


class TestDiscardSemantics(unittest.TestCase):
    def test_shanten_is_still_the_primary_key(self):
        hand = ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "南", "西"]
        pick = _pick_discard_route(list(hand), "西", 0, 0)
        best = _best_discard_realukeire(list(hand), "西", 0, 0)
        h_pick = [c for c in hand if c != pick]
        h_best = [c for c in hand if c != best]
        self.assertLessEqual(exact_shanten(h_pick, qidui=False),
                             exact_shanten(h_best, qidui=False),
                             "候选不得选比 C135 更差的向听")

    def test_returns_a_tile_from_hand(self):
        hand = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南", "西"]
        self.assertIn(_pick_discard_route(list(hand), "西", 0, 0), hand)

    def test_deterministic(self):
        hand = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南", "西"]
        self.assertEqual(_pick_discard_route(list(hand), "西", 0, 0),
                         _pick_discard_route(list(hand), "西", 0, 0))


class TestClass(unittest.TestCase):
    def test_is_registered_and_subclasses_c150(self):
        from bot.speedc150 import SpeedC150
        self.assertTrue(issubclass(SpeedC151, SpeedC150))
        self.assertTrue(hasattr(SpeedC151(), "_pick_discard"))
        self.assertEqual(ROUTE_BONUS, 8.0)


if __name__ == "__main__":
    unittest.main()
