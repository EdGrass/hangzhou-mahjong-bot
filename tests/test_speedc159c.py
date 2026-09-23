# -*- coding: utf-8 -*-
"""speedc159c（早期反向档：前 3 巡负权重）单测。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc159 import SpeedC159, phase_weight, W_CONSERVATIVE   # noqa: E402
from bot.speedc159c import SpeedC159C, W_EARLY_NEG                  # noqa: E402

HAND = ["9b", "2w", "7w", "7b", "1b", "2w", "东", "1w", "4w", "1b", "东", "1b", "3w", "8w"]
DRAWN = "8w"


def _view(river_len):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(HAND), "melds": [],
            "drawn_tile": DRAWN, "river": [], "river_len": river_len, "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC159C(unittest.TestCase):
    def test_weights_negative_early(self):
        self.assertEqual(W_EARLY_NEG, (-0.3, 1.0, 1.5))
        self.assertLess(W_EARLY_NEG[0], 0.0, "前 3 巡必须为负（偏好保对子）")
        self.assertEqual(phase_weight(4, W_EARLY_NEG), -0.3)
        self.assertEqual(phase_weight(16, W_EARLY_NEG), 1.0)
        self.assertEqual(phase_weight(40, W_EARLY_NEG), 1.5)
        self.assertEqual(SpeedC159C().weights, W_EARLY_NEG)

    def test_mid_late_same_as_c159(self):
        for rl in (16, 40):
            self.assertEqual(phase_weight(rl, W_EARLY_NEG), phase_weight(rl, W_CONSERVATIVE),
                             "只改早期：中/末盘必须与 c159 相同")

    def test_behaviour_on_fixture(self):
        pol = SpeedC159C()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(16)), "2w")
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(40)), "2w")
        # 早盘（负权重）仍选择与 c150/c159 相同的 1w（该夹具上不会反过来拆对）
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(4)), "1w")
