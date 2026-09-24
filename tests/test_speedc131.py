# -*- coding: utf-8 -*-
"""SpeedC131 单测：确认它是 speedtugc 的**单变量**候选（只差 god_meld），
且该开关真的被传进弃牌搜索——防止将来重构时静默退回 tugc 行为。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot.speedtugc as stc                      # noqa: E402
from bot.speedtugc import SpeedTUGC               # noqa: E402
from bot.speedc131 import SpeedC131               # noqa: E402


def _draw_view(tiles):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(tiles), "melds": [], "drawn_tile": tiles[-1],
            "offer_tile": None, "god": {"baotou": False, "chain_count": 0,
                                        "catch_play": False}, "all_melds": []}


class TestSpeedC131(unittest.TestCase):
    def setUp(self):
        self._orig = stc._best_discard_t
        self.seen = []

    def tearDown(self):
        stc._best_discard_t = self._orig

    def _capture(self, strat):
        def fake(hand, drawn, exposed, gangs, god_meld=True):
            self.seen.append(god_meld)
            return hand[0]
        stc._best_discard_t = fake
        act = strat.decide(_draw_view(["1w", "2w", "3w", "5b", "6b", "7b",
                                       "1t", "2t", "3t", "东", "南", "西", "白", "9b"]))
        return act

    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc131", F)
        self.assertIsInstance(F["speedc131"](), SpeedC131)

    def test_c131_passes_god_meld_false(self):
        act = self._capture(SpeedC131())
        self.assertEqual(self.seen, [False])
        self.assertEqual(act["action"], "discard")

    def test_tugc_passes_god_meld_true(self):
        act = self._capture(SpeedTUGC())
        self.assertEqual(self.seen, [True])
        self.assertEqual(act["action"], "discard")

    def test_only_difference_is_the_flag(self):
        """类属性层面的单变量保证：其余行为都由同一套 decide 提供。"""
        self.assertIs(SpeedC131.decide, SpeedTUGC.decide)
        self.assertTrue(SpeedTUGC.GOD_MELD)
        self.assertFalse(SpeedC131.GOD_MELD)


if __name__ == "__main__":
    unittest.main()
