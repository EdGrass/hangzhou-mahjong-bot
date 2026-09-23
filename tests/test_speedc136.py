# -*- coding: utf-8 -*-
"""SpeedC136 单测：副露门控的**质量感知**版本。

用两个**真机窗口**做 fixture：
  ① 严格门控 pass、`speedtug`(allow_equal) 会收、**c136 也收**（因为它确实让真进张变好）；
  ② 严格门控 pass、`speedtug` 会收、**c136 拒**（向听不变但真进张没变好）。
第 ② 条是本候选与 `speedtug` 的本质区别，必须钉住。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedtugc import SpeedTUGC          # noqa: E402
from bot.speedtug import SpeedTUG            # noqa: E402
from bot.speedc136 import SpeedC136          # noqa: E402

# 真机窗口 ①：c136 应收下（真进张变好）
FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
# 真机窗口 ②：c136 应拒绝（speedtug 会无差别收下）
FIX2 = ("response_chi", "1b",
        ["8t", "2b", "5w", "1b", "8w", "8t", "2t", "3b", "5w", "6t", "2b", "2b", "1w"], [])


def _view(phase, offer, hand, melds):
    return {"seat": 0, "phase": phase, "turn": 1, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "god_discarder_seat": -1}, "all_melds": []}


class TestSpeedC136(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc136", F)
        self.assertIsInstance(F["speedc136"](), SpeedC136)

    def test_baseline_unchanged(self):
        """钩子默认必须等于原严格判据（否则会悄悄改动正在跑的基线）。"""
        act = SpeedTUGC().decide(_view(*FIX1))
        self.assertEqual(act.get("action"), "pass")

    def test_accepts_when_real_ukeire_improves(self):
        act = SpeedC136().decide(_view(*FIX1))
        self.assertEqual(act.get("action"), "peng")
        self.assertEqual(act.get("tile"), "5t")

    def test_rejects_when_quality_does_not_improve(self):
        """关键区分：allow_equal 会收，但 c136 因为"真进张没变好"而拒绝。"""
        self.assertEqual(SpeedTUG().decide(_view(*FIX2)).get("action"), "chi")
        self.assertEqual(SpeedC136().decide(_view(*FIX2)).get("action"), "pass")

    def test_only_difference_is_the_claim_hook(self):
        self.assertIs(SpeedC136.decide, SpeedTUGC.decide)
        self.assertIsNot(SpeedC136._want_claim, SpeedTUGC._want_claim)


if __name__ == "__main__":
    unittest.main()
