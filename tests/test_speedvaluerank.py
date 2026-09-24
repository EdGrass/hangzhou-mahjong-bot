# -*- coding: utf-8 -*-
"""`bot/speedvaluerank.SpeedValueRank` 契约测试（R1207）——役 5 候选（教师排序器）。

四条不变量：
  ① 排序器缺失 ⇒ 逐位等于 `SpeedValue`；
  ② 基线不在"弃后最小向听组"内 ⇒ 绝不改（单变量域）；
  ③ margin 闸门双向；异常回落；
  ④ 只覆盖 `_pick_discard`（不碰胡/杠/副露窗口），且排序器已加载。
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                # noqa: E402
from bot.speedvaluerank import SpeedValueRank        # noqa: E402


def _view(hand, drawn=None, melds=None, river=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": list(melds or []),
            "all_melds": [], "river": list(river or []), "river_len": len(river or []),
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


HAND = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']


class SpeedValueRankTest(unittest.TestCase):
    def setUp(self):
        self.base = SpeedValue()
        self.cand = SpeedValueRank()

    def test_no_ranker_is_identity(self):
        self.cand.ranker = None
        v = _view(HAND, None)
        self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v),
                         self.base._pick_discard(list(HAND), None, 0, 0, view=v))

    def test_exception_falls_back(self):
        v = _view(HAND, None)
        with mock.patch.object(self.cand, "_min_shanten_group", side_effect=RuntimeError("boom")):
            got = self.cand._pick_discard(list(HAND), None, 0, 0, view=v)
        self.assertEqual(got, self.base._pick_discard(list(HAND), None, 0, 0, view=v))

    def test_base_outside_group_never_changes(self):
        v = _view(HAND, None)
        base = self.base._pick_discard(list(HAND), None, 0, 0, view=v)
        with mock.patch.object(self.cand, "_min_shanten_group", return_value=["1w"]):
            self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v), base)

    def test_margin_gate_both_ways(self):
        v = _view(HAND, None)
        base = self.base._pick_discard(list(HAND), None, 0, 0, view=v)
        other = next(d for d in HAND if d != base)
        group = [base, other]
        with mock.patch.object(self.cand, "_min_shanten_group", return_value=group), \
                mock.patch.object(self.cand.ranker, "order", return_value=[other, base]), \
                mock.patch.object(self.cand.ranker, "score", return_value=[0.0, 1.0]):
            self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v), other)
        with mock.patch.object(self.cand, "_min_shanten_group", return_value=group), \
                mock.patch.object(self.cand.ranker, "order", return_value=[other, base]), \
                mock.patch.object(self.cand.ranker, "score", return_value=[1.0, 0.0]):
            self.assertEqual(self.cand._pick_discard(list(HAND), None, 0, 0, view=v), base)

    def test_discard_only_and_ranker_loaded(self):
        self.assertNotIn("_want_claim", SpeedValueRank.__dict__)
        self.assertIsNotNone(self.cand.ranker)


if __name__ == "__main__":
    unittest.main()
