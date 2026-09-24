# -*- coding: utf-8 -*-
"""c180/c181 终极组合单测：BC 弃牌 + full c136 + c165 学习副露 + c144/c141。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc141 import SpeedC141
from bot.speedc147 import SpeedC147
from bot.speedc165 import SpeedC165
from bot.speedc180 import SpeedC180
from bot.speedc181 import SpeedC181

PLAIN = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
         "东", "东", "东", "南", "南"]


def _view(hand, drawn):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestUltimateCombo(unittest.TestCase):
    def test_hooks(self):
        self.assertIs(SpeedC180._want_claim, SpeedC165._want_claim)
        self.assertIs(SpeedC180.decide, SpeedC147.decide)
        self.assertIs(SpeedC180._best_giveup, SpeedC141._best_giveup)
        self.assertTrue(SpeedC180().SELF_GANG)
        self.assertTrue(hasattr(SpeedC180(), "model"))
        self.assertTrue(hasattr(SpeedC180(), "_mnet"))

    def test_true_variant_flags_and_gate(self):
        p = SpeedC181()
        self.assertTrue(p.YOU_CAI_BI_KAO)
        self.assertFalse(p.GOD_MELD)
        self.assertTrue(p.FORCE_BAOTOU_ON_BLOCK)
        act = p.decide(_view(PLAIN, "南")) or {}
        self.assertEqual(act.get("action"), "discard")

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('"speedc180"', s)
        self.assertIn('"speedc181"', s)


if __name__ == "__main__":
    unittest.main()
