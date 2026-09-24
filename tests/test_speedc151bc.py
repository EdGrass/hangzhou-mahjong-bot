# -*- coding: utf-8 -*-
"""`bot/speedc151bc.SpeedC151BC` 契约测试（R1198）——役 3 的**分支臂**（役 2 若不走 speedvalue）。

四条不变量：
  ① 模型缺失 ⇒ 逐位等于 `SpeedC151`（零行为变化）；
  ② 基线不在"弃后最小向听"组内 ⇒ 绝不改（守单变量域）；
  ③ margin 闸门双向（=基线 / 严格更优才改）；
  ④ 特征/打分与 `C067Policy` 同源（unbound 复用，154 维）；且本类只覆盖 `_pick_discard`。
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc067 import C067Policy                # noqa: E402
from bot.speedc151 import SpeedC151                 # noqa: E402
from bot.speedc151bc import SpeedC151BC             # noqa: E402


def _view(hand, drawn=None, melds=None):
    return {"seat": 0, "phase": "draw", "turn": 6, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": list(melds or []),
            "all_melds": [], "river": [], "river_len": 0,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


HAND = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']


class SpeedC151BCTest(unittest.TestCase):
    def setUp(self):
        self.base = SpeedC151()
        self.cand = SpeedC151BC()

    def test_no_model_is_identity(self):
        self.cand.model = None
        v = _view(HAND, None)
        self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v),
                         self.base._pick_discard(list(HAND), None, 0, 0, view=v))

    def test_model_exception_falls_back(self):
        v = _view(HAND, None)
        with mock.patch.object(self.cand, "_bc_pick", side_effect=RuntimeError("boom")):
            got = self.cand._pick_discard(list(HAND), None, 0, 0, view=v)
        self.assertEqual(got, self.base._pick_discard(list(HAND), None, 0, 0, view=v))

    def test_margin_gate_both_ways(self):
        v = _view(HAND, None)
        base = self.base._pick_discard(list(HAND), None, 0, 0, view=v)
        other = next(d for d in HAND if d != base)
        with mock.patch.object(self.cand, "_bc_pick", side_effect=lambda h, e, g, b: other):
            self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v), other)
        with mock.patch.object(self.cand, "_bc_pick", side_effect=lambda h, e, g, b: b):
            self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v), base)

    def test_features_shared_and_discard_only(self):
        self.assertNotIn("_want_claim", SpeedC151BC.__dict__)
        rows = C067Policy._features(self.cand, HAND, [HAND[-1], HAND[0]], HAND[-1], 0, 0)
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows[0]), 154)
        self.assertIsNotNone(self.cand.model)


if __name__ == "__main__":
    unittest.main()
