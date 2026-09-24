# -*- coding: utf-8 -*-
"""speedc159b（分时段压对数的**加力档**）单测：只改中/末盘权重，早盘与 c159 一致。"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc159 import SpeedC159, phase_weight, W_CONSERVATIVE, W_FORCE   # noqa: E402
from bot.speedc159b import SpeedC159B                                        # noqa: E402

HAND = ["9b", "2w", "7w", "7b", "1b", "2w", "东", "1w", "4w", "1b", "东", "1b", "3w", "8w"]
DRAWN = "8w"


def _view(river_len):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(HAND), "melds": [],
            "drawn_tile": DRAWN, "river": [], "river_len": river_len, "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC159B(unittest.TestCase):
    def test_weights(self):
        self.assertEqual(W_FORCE, (0.0, 1.5, 2.5))
        self.assertEqual(phase_weight(4, W_FORCE), 0.0)
        self.assertEqual(phase_weight(16, W_FORCE), 1.5)
        self.assertEqual(phase_weight(40, W_FORCE), 2.5)
        self.assertEqual(SpeedC159B().weights, W_FORCE)
        self.assertEqual(SpeedC159().weights, W_CONSERVATIVE)

    def test_only_mid_late_differ(self):
        self.assertEqual(phase_weight(4, W_FORCE), phase_weight(4, W_CONSERVATIVE),
                         "早盘（前 3 巡）两档必须一致 = 都不压对数")
        self.assertGreater(phase_weight(16, W_FORCE), phase_weight(16, W_CONSERVATIVE))
        self.assertGreater(phase_weight(40, W_FORCE), phase_weight(40, W_CONSERVATIVE))

    def test_behaviour_on_fixture(self):
        pol = SpeedC159B()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(4)), "1w",
                         "早盘应像 c150（不压对数）")
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(16)), "2w",
                         "中盘应像 c151（压对数）")
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(40)), "2w")

    def test_no_mutable_global(self):
        import sys as _s
        src = inspect.getsource(_s.modules[SpeedC159B.__module__])
        self.assertNotIn("global ", src)
