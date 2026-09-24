# -*- coding: utf-8 -*-
"""speedc154（庄位条件化）单测：**唯一差别**是"做庄时不弃胡换爆头"。

夹具是**搜索得到的最小可区分样例**（`var/_find_giveup_fixture.py`）：
`hand=['白','白','6t','中','中','中','7t','8t','9t','4b','5b','6b','5w','5w'], drawn='5w'`
—— c151/C036 判"弃 6t 去换爆头更划算"，所以它**放弃这一胡**。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import SpeedC151                     # noqa: E402
from bot.speedc154 import SpeedC154                     # noqa: E402

GIVEUP_HAND = ["白", "白", "6t", "中", "中", "中", "7t", "8t", "9t",
               "4b", "5b", "6b", "5w", "5w"]
GIVEUP_DRAWN = "5w"
GIVEUP_TILE = "6t"      # c151 在有胡的情况下选的弃牌


def _view(dealer, seat=0):
    return {"seat": seat, "phase": "draw", "turn": seat, "responding_seats": [],
            "my_hand": list(GIVEUP_HAND), "melds": [], "drawn_tile": GIVEUP_DRAWN,
            "offer_tile": None, "river": [], "river_len": 8, "all_melds": [],
            "can_gang": True, "dealer": dealer,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC154SeatConditional(unittest.TestCase):
    def test_fixture_is_discriminating(self):
        """先证夹具有效：父臂（c151）在**做庄**时依然弃胡。"""
        act = SpeedC151().decide(_view(dealer=0))
        self.assertEqual(act.get("action"), "discard")
        self.assertEqual(act.get("tile"), GIVEUP_TILE)

    def test_dealer_takes_the_win(self):
        act = SpeedC154().decide(_view(dealer=0))
        self.assertEqual(act.get("action"), "hu", "做庄时不该拿现成的一胡去赌爆头")

    def test_nondealer_keeps_c036(self):
        act = SpeedC154().decide(_view(dealer=1))
        self.assertEqual(act.get("action"), "discard")
        self.assertEqual(act.get("tile"), GIVEUP_TILE, "做闲时必须与 c151/C036 完全一致")

    def test_unknown_dealer_is_conservative(self):
        for dealer in (None, "x", -1):
            act = SpeedC154().decide(_view(dealer=dealer))
            self.assertEqual(act.get("action"), "discard", "庄家未知 ⇒ 退回 c151 行为")

    def test_pick_discard_not_overridden(self):
        """方向护栏：本臂**不得**改弃牌层（只改"要不要弃胡"）。"""
        self.assertIs(SpeedC154._pick_discard, SpeedC151._pick_discard)

    def test_source_guardrails(self):
        src = inspect.getsource(SpeedC154)
        self.assertIn("_best_giveup", src)
        self.assertIn("super()._best_giveup(", src)
        self.assertIn("_is_dealer_now", src)
