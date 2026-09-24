# -*- coding: utf-8 -*-
"""`bot/speedvalueplain.SpeedValuePlain` 契约测试（R1215）——投影片：只换出牌器。

四条不变量：
  ① 出牌器 === `SpeedTUGC._pick_discard`（纯进张口径）；
  ② 相对 `SpeedValue` **只覆盖 `_pick_discard`**（不碰 claim/gang/giveup 层）；
  ③ 纯进张器抛异常时**回落到 `SpeedValue` 自己的选择**；
  ④ 类层面只定义 `_pick_discard` 与 `__init__`。
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedtugc import SpeedTUGC                  # noqa: E402
from bot.speedvalue import SpeedValue                # noqa: E402
from bot.speedvalueplain import SpeedValuePlain      # noqa: E402


def _view(hand, drawn=None, melds=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": list(melds or []),
            "all_melds": [], "river": [], "river_len": 0,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


HANDS = [
    (['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t'], '9t'),
    (['1w', '1w', '2w', '3w', '5b', '5b', '6b', '7b', '2t', '3t', '4t', '8t', '9t', '白'], None),
    (['2b', '3b', '4b', '6t', '7t', '8t', '5w', '5w', '9b', '1t', '1t', '3w', '4w', '白'], '白'),
]


class SpeedValuePlainTest(unittest.TestCase):
    def setUp(self):
        self.base = SpeedValue()
        self.cand = SpeedValuePlain()

    def test_discard_equals_plain_chooser(self):
        for hand, drawn in HANDS:
            v = _view(hand, drawn)
            self.assertEqual(self.cand._pick_discard(list(hand), drawn, 0, 0, view=v),
                             SpeedTUGC._pick_discard(self.cand, list(hand), drawn, 0, 0, view=v))

    def test_only_pick_discard_overridden(self):
        self.assertNotIn("_want_claim", SpeedValuePlain.__dict__)
        self.assertNotIn("_best_giveup", SpeedValuePlain.__dict__)
        self.assertIn("_pick_discard", SpeedValuePlain.__dict__)

    def test_exception_falls_back_to_speedvalue(self):
        hand, drawn = HANDS[0]
        v = _view(hand, drawn)
        with mock.patch.object(SpeedTUGC, "_pick_discard", side_effect=RuntimeError("boom")):
            got = self.cand._pick_discard(list(hand), drawn, 0, 0, view=v)
        self.assertEqual(got, self.base._pick_discard(list(hand), drawn, 0, 0, view=v))

    def test_class_surface_is_minimal(self):
        # 允许 ABCMeta 注入的 `_abc_impl`；实质重写只应有 `_pick_discard`
        own = [k for k in SpeedValuePlain.__dict__ if not k.startswith("__") and k != "_abc_impl"]
        self.assertEqual(sorted(own), ["_pick_discard"])


if __name__ == "__main__":
    unittest.main()
