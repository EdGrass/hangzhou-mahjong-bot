# -*- coding: utf-8 -*-
"""c173~c176：fast 基底 + c144/c141（杠/财飘修正）束单测。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc141 import SpeedC141
from bot.speedc144 import SpeedC144
from bot.speedc164 import SpeedC164
from bot.speedc165 import SpeedC165
from bot.speedc166 import SpeedC166
from bot.speedc173 import SpeedC173
from bot.speedc174 import SpeedC174
from bot.speedc175 import SpeedC175
from bot.speedc176 import SpeedC176

PLAIN = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
         "东", "东", "东", "南", "南"]


def _view(hand, drawn):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestFastBundle(unittest.TestCase):
    def test_core_hooks(self):
        self.assertIs(SpeedC173._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC173._best_giveup, SpeedC141._best_giveup)
        self.assertIs(SpeedC173._pick_discard, SpeedC164._pick_discard)
        self.assertIs(SpeedC174._pick_discard, SpeedC165._pick_discard)
        self.assertIs(SpeedC175._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC175._pick_discard, SpeedC166._pick_discard)

    def test_self_gang_and_ultimate_flags(self):
        for C in (SpeedC173, SpeedC174, SpeedC175, SpeedC176):
            self.assertTrue(C().SELF_GANG)
        self.assertFalse(SpeedC176().GOD_MELD)
        self.assertTrue(SpeedC176().YOU_CAI_BI_KAO)
        self.assertTrue(SpeedC176().FORCE_BAOTOU_ON_BLOCK)

    def test_ultimate_blocks_plain_joker_hu(self):
        act = SpeedC176().decide(_view(PLAIN, "南")) or {}
        self.assertEqual(act.get("action"), "discard")

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        for name in ("speedc173", "speedc174", "speedc175", "speedc176"):
            self.assertIn('"%s"' % name, s)


if __name__ == "__main__":
    unittest.main()
