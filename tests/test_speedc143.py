# -*- coding: utf-8 -*-
"""SpeedC143 单测：低延迟组合臂 = C136（质量副露）+ C141（财飘），**不含 C135**。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc136 import SpeedC136        # noqa: E402
from bot.speedc141 import SpeedC141        # noqa: E402
from bot.speedc143 import SpeedC143        # noqa: E402
from bot.speedtugc import SpeedTUGC        # noqa: E402

A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
FIX2 = ("response_chi", "1b",
        ["8t", "2b", "5w", "1b", "8w", "8t", "2t", "3b", "5w", "6t", "2b", "2b", "1w"], [])
F_HAND = ["1b", "2b", "6w", "7w", "8b", "9b", "9b", "9w", "白", "西", "西"]


def _view(phase, offer, hand, melds):
    return {"seat": 0, "phase": phase, "turn": 1, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestSpeedC143(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc143", F)
        self.assertIsInstance(F["speedc143"](), SpeedC143)

    def test_discard_path_is_pure_baseline(self):
        """低延迟的意义：出牌钩子必须仍是 SpeedTUGC 的（不做真进张计算）。"""
        self.assertIs(SpeedC143._pick_discard, SpeedTUGC._pick_discard)
        self.assertIs(SpeedC143.decide, SpeedTUGC.decide)
        self.assertEqual(SpeedC143()._pick_discard(list(F_HAND), "白", 1, 0), "6w")

    def test_c136_component(self):
        for fix in (FIX1, FIX2):
            self.assertEqual(SpeedC143().decide(_view(*fix)), SpeedC136().decide(_view(*fix)))
        self.assertEqual(SpeedC143().decide(_view(*FIX1)).get("action"), "peng")
        self.assertEqual(SpeedC143().decide(_view(*FIX2)).get("action"), "pass")

    def test_c141_component(self):
        ch = {"count": 0, "piao": 0}
        self.assertEqual(SpeedC143()._best_giveup(list(A_HAND), 2, 0, 2, ch), "白")
        self.assertEqual(SpeedC143()._best_giveup(list(A_HAND), 2, 0, 2, ch),
                         SpeedC141()._best_giveup(list(A_HAND), 2, 0, 2, ch))
        v = _view("draw", None, A_HAND, A_MELDS)
        v["turn"] = 0
        v["drawn_tile"] = A_DRAWN
        act = SpeedC143().decide(v)
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))
        self.assertEqual(SpeedTUGC().decide(v).get("action"), "hu")


if __name__ == "__main__":
    unittest.main()
