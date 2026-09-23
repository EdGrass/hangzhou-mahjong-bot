# -*- coding: utf-8 -*-
"""C063 SpeedSearch 单元测试：赔付、未见牌池、缓存与合法回退。"""
import unittest

from mahjong.sim import make_view
from mahjong.tiles import counts_of

import bot.speedsearch as m


class TestSpeedSearchHelpers(unittest.TestCase):
    def setUp(self):
        m._best_discard_cached.cache_clear()
        m._win_cached.cache_clear()

    def test_payout_dealer_and_nondealer(self):
        self.assertEqual(m._payout(2, 0, 0), 48.0)
        self.assertEqual(m._payout(2, 0, 1), 20.0)
        self.assertEqual(m._payout(1, None, 1), 10.0)

    def test_unseen_pool_excludes_public_tiles(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "1b", "2b", "3b", "东", "南"]
        view = make_view(
            0, "draw", 0, hand, melds=[],
            river=["1t"],
            all_melds=[[], [{"type": "peng", "tile": "2t",
                             "tiles": ["2t", "2t", "2t"]}], [], []],
            dealer=0,
        )
        pool = m._unseen_pool(hand, view)
        # 2t 的 3 张在副露中，牌池只剩 1 张；1t 在河里也不可再摸。
        self.assertEqual(pool.count("2t"), 1)
        self.assertEqual(pool.count("1t"), 3)

    def test_cached_helpers_are_legal(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "1b", "2b", "3b", "东", "南"]
        tile = m._best_discard_cached(tuple(counts_of(hand)), None, 0, 0)
        self.assertIn(tile, hand)
        self.assertIsInstance(m._win_cached(tuple(counts_of(hand)), 0, 0), bool)

    def test_decide_returns_legal_discard(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "1b", "2b", "3b", "东", "南"]
        view = make_view(0, "draw", 0, hand, melds=[], river=[],
                         all_melds=[[], [], [], []], dealer=0)
        st = m.SpeedSearch(samples=2, horizon=2, max_candidates=2,
                           min_samples=1, min_gain=999.0,
                           time_budget_ms=50)
        act = st.decide(view)
        self.assertEqual(act.get("action"), "discard")
        self.assertIn(act.get("tile"), hand)

    def test_sim_view_carries_dealer(self):
        view = make_view(2, "draw", 2, ["1w"] * 13, melds=[], river=[],
                         all_melds=[[], [], [], []], dealer=2)
        self.assertEqual(view["dealer"], 2)


if __name__ == "__main__":
    unittest.main()