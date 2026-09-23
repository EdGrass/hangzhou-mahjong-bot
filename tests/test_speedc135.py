# -*- coding: utf-8 -*-
"""SpeedC135 单测：未听牌并列改按**真进张**（bot/ukeire.py）打破。

真机盘（从 `var/replays/*` 全信息复盘抽出）：基线弃 6w，c135 弃 9w。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc135 import SpeedC135, _best_discard_realukeire   # noqa: E402
from bot.speedt import _best_discard_t                          # noqa: E402

# 真机盘（1 副露）：基线 6w vs c135 9w
F_HAND = ["1b", "2b", "6w", "7w", "8b", "9b", "9b", "9w", "白", "西", "西"]
F_DRAWN = "白"
F_EX, F_GG = 1, 0

# 真机盘（门清）：基线 3w vs c135 8b
G_HAND = ["2t", "3b", "3t", "3w", "4b", "4b", "4t", "5b", "6w", "6w", "8b", "8t", "白", "白"]
G_DRAWN = "5b"


class TestSpeedC135(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc135", F)
        self.assertIsInstance(F["speedc135"](), SpeedC135)

    def test_only_difference_is_discard_hook(self):
        from bot.speedtugc import SpeedTUGC
        self.assertIs(SpeedC135.decide, SpeedTUGC.decide)
        self.assertIsNot(SpeedC135._pick_discard, SpeedTUGC._pick_discard)

    def test_real_fixture_with_melds(self):
        self.assertEqual(_best_discard_t(list(F_HAND), F_DRAWN, F_EX, F_GG), "6w")
        self.assertEqual(
            _best_discard_realukeire(list(F_HAND), F_DRAWN, F_EX, F_GG, view=None), "9w")

    def test_real_fixture_closed_hand(self):
        self.assertEqual(_best_discard_t(list(G_HAND), G_DRAWN, 0, 0), "3w")
        self.assertEqual(
            _best_discard_realukeire(list(G_HAND), G_DRAWN, 0, 0, view=None), "8b")


if __name__ == "__main__":
    unittest.main()
