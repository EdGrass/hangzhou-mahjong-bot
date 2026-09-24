# -*- coding: utf-8 -*-
"""c169~c172：快版 YouCaiBiKao 合法胡闸门单测。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc164 import SpeedC164
from bot.speedc165 import SpeedC165
from bot.speedc169 import SpeedC169
from bot.speedc170 import SpeedC170
from bot.speedc171 import SpeedC171
from bot.speedc172 import SpeedC172

PLAIN = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
         "东", "东", "东", "南", "南"]
PLAIN_DRAWN = "南"
BAOTOU = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白", "5b"]


def _view(hand, drawn, chain=0, piao=0):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": chain, "catch_play": False,
                    "piao_count": piao, "god_discarder_seat": -1}}


class TestFastYCBK(unittest.TestCase):
    def test_flags(self):
        for C in (SpeedC169, SpeedC170, SpeedC171, SpeedC172):
            p = C()
            self.assertFalse(p.GOD_MELD)
            self.assertTrue(p.YOU_CAI_BI_KAO)

    def test_plain_joker_hu_blocked(self):
        for C in (SpeedC169, SpeedC170, SpeedC171, SpeedC172):
            act = C().decide(_view(PLAIN, PLAIN_DRAWN)) or {}
            self.assertEqual(act.get("action"), "discard", C.__name__)

    def test_baotou_allowed(self):
        for C in (SpeedC169, SpeedC170, SpeedC171, SpeedC172):
            act = C().decide(_view(BAOTOU, "5b")) or {}
            self.assertEqual(act.get("action"), "hu", C.__name__)

    def test_chain_allowed(self):
        act = SpeedC169().decide(_view(PLAIN, PLAIN_DRAWN, chain=1)) or {}
        self.assertEqual(act.get("action"), "hu")

    def test_hooks(self):
        self.assertIs(SpeedC169._pick_discard, SpeedC164._pick_discard)
        self.assertIs(SpeedC170._want_claim, SpeedC165._want_claim)
        self.assertIs(SpeedC171._pick_discard, SpeedC164._pick_discard)
        self.assertIs(SpeedC171._want_claim, SpeedC165._want_claim)
        self.assertTrue(SpeedC172().FORCE_BAOTOU_ON_BLOCK)
        self.assertFalse(SpeedC171().FORCE_BAOTOU_ON_BLOCK)

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        for name in ("speedc169", "speedc170", "speedc171", "speedc172"):
            self.assertIn('"%s"' % name, s)


if __name__ == "__main__":
    unittest.main()
