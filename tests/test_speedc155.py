# -*- coding: utf-8 -*-
"""speedc155（庄位条件化的路线项）单测。

夹具来自真机 dec 流（`var/_find_route_fixture.py` 搜索得到）：
`hand=['9b','2w','7w','7b','1b','2w','东','1w','4w','1b','东','1b','3w','8w'], drawn='8w'`
—— c150（无路线项）弃 **1w**、c151（多对子惩罚）弃 **2w** ⇒ 可区分。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc150 import SpeedC150                       # noqa: E402
from bot.speedc151 import SpeedC151                       # noqa: E402
from bot.speedc155 import SpeedC155                       # noqa: E402

HAND = ["9b", "2w", "7w", "7b", "1b", "2w", "东", "1w", "4w", "1b", "东", "1b", "3w", "8w"]
DRAWN = "8w"
TILE_C150 = "1w"
TILE_C151 = "2w"


def _view(dealer, seat=0):
    v = {"seat": seat, "phase": "draw", "turn": seat, "my_hand": list(HAND),
         "melds": [], "drawn_tile": DRAWN, "river": [], "river_len": 6, "all_melds": [],
         "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                 "piao_count": 0, "god_discarder_seat": -1}}
    if dealer is not None:
        v["dealer"] = dealer
    return v


class TestC155SeatConditionalRoute(unittest.TestCase):
    def test_fixture_discriminates_parents(self):
        self.assertEqual(SpeedC150()._pick_discard(HAND, DRAWN, 0, 0), TILE_C150)
        self.assertEqual(SpeedC151()._pick_discard(HAND, DRAWN, 0, 0), TILE_C151)

    def test_dealer_uses_route_penalty(self):
        pol = SpeedC155()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(dealer=0, seat=0)),
                         TILE_C151, "做庄应保留 c151 的多对子惩罚（换速度）")

    def test_nondealer_uses_no_penalty(self):
        pol = SpeedC155()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(dealer=1, seat=0)),
                         TILE_C150, "做闲应退回 c150（保对子/价值）")

    def test_unknown_dealer_falls_back_to_c150(self):
        pol = SpeedC155()
        for dealer in (None, "x", -1):
            self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(dealer=dealer)),
                             TILE_C150, "庄家未知 ⇒ 退回无惩罚（保守）")
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=None), TILE_C150)

    def test_does_not_override_decide(self):
        """方向护栏：本臂只动弃牌层的座位条件，不动胡牌/副露/杠等其它层。"""
        self.assertIs(SpeedC155.decide, SpeedC151.decide)
        self.assertIs(SpeedC155._want_claim if hasattr(SpeedC155, "_want_claim") else None,
                      SpeedC151._want_claim if hasattr(SpeedC151, "_want_claim") else None)

    def test_source_guardrails(self):
        src = inspect.getsource(SpeedC155)
        self.assertIn("SpeedC151._pick_discard", src)
        self.assertIn("SpeedC150._pick_discard", src)
        self.assertIn("dealer", src)
