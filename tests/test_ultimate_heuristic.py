# -*- coding: utf-8 -*-
"""c183/c184：终极启发式束（c164 route + c165 学习副露 + c136 质量门控 + c144/c141）。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc136 import SpeedC136
from bot.speedc141 import SpeedC141
from bot.speedc144 import SpeedC144
from bot.speedc164 import SpeedC164
from bot.speedc165 import SpeedC165
from bot.speedc183 import SpeedC183
from bot.speedc184 import SpeedC184

FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
PLAIN = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
         "东", "东", "东", "南", "南"]


def _view(rec):
    ph, o, h, m = rec
    return {"seat": 0, "phase": ph, "turn": 1, "responding_seats": [0],
            "my_hand": list(h), "melds": list(m), "drawn_tile": None,
            "offer_tile": o, "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "god_discarder_seat": -1}}


def _draw(hand, drawn="南"):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestUltimateHeuristic(unittest.TestCase):
    def test_hooks(self):
        self.assertIs(SpeedC183._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC183._pick_discard, SpeedC164._pick_discard)
        self.assertIs(SpeedC183._best_giveup, SpeedC141._best_giveup)
        self.assertTrue(SpeedC183().SELF_GANG)
        self.assertIs(SpeedC184._want_claim, SpeedC144._want_claim)

    def test_c136_fixture_still_accepts(self):
        act = SpeedC183().decide(_view(FIX1)) or {}
        self.assertEqual(act.get("action"), "peng")

    def test_true_variant_gate_and_flags(self):
        p = SpeedC184()
        self.assertTrue(p.YOU_CAI_BI_KAO)
        self.assertFalse(p.GOD_MELD)
        self.assertTrue(p.FORCE_BAOTOU_ON_BLOCK)
        act = p.decide(_draw(PLAIN)) or {}
        self.assertEqual(act.get("action"), "discard")

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('"speedc183"', s)
        self.assertIn('"speedc184"', s)


if __name__ == "__main__":
    unittest.main()
