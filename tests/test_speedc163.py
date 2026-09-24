# -*- coding: utf-8 -*-
"""SpeedC163 单测：只组合 c159 的出牌钩子与 c156 的副露钩子，C036 链不旁路。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc141 import SpeedC141                 # noqa: E402
from bot.speedc156 import SpeedC156                 # noqa: E402
from bot.speedc159 import SpeedC159                 # noqa: E402
from bot.speedc163 import SpeedC163                 # noqa: E402


class TestC163Composition(unittest.TestCase):
    def test_mro_order(self):
        mro = SpeedC163.__mro__
        self.assertLess(mro.index(SpeedC159), mro.index(SpeedC156),
                        "必须先取 c159 的出牌钩子，再由 c156 的副露钩子接链")

    def test_hooks_are_taken_from_expected_classes(self):
        self.assertIs(SpeedC163._pick_discard, SpeedC159._pick_discard)
        self.assertIs(SpeedC163._want_claim, SpeedC156._want_claim)

    def test_keeps_c036(self):
        self.assertIs(SpeedC163._best_giveup, SpeedC141._best_giveup,
                      "组合臂不得旁路 C036 弃胡换爆头")

    def test_learned_meld_hook_works_through_mro(self):
        view = {"seat": 0, "phase": "response_peng", "turn": 1,
                "my_hand": ["8t", "西", "1t", "9b", "9t", "9w", "9t", "东", "5b", "西", "东", "2w", "8t"],
                "melds": [], "offer_tile": "9t", "river": ["5w", "东", "中", "2t", "1t"], "all_melds": [],
                "god": {"baotou": False, "chain_count": 0, "catch_play": False, "piao_count": 0,
                        "god_discarder_seat": -1}}
        self.assertTrue(SpeedC163()._want_claim(view, "peng", None),
                        "组合臂的 super() 链必须还能走到 c156 的学习副露钩子")

    def test_instance_has_both_knobs(self):
        p = SpeedC163()
        self.assertEqual(p.name, "speedc163")
        self.assertEqual(tuple(p.weights), tuple(SpeedC159.WEIGHTS))
        self.assertAlmostEqual(p.claim_p, 0.60)
        self.assertTrue(hasattr(p, "_mnet"))

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            self.assertIn('"speedc163"', fh.read())


if __name__ == "__main__":
    unittest.main()
