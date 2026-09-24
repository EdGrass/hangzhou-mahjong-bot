# -*- coding: utf-8 -*-
"""speedc159（分时段压对数）单测。

夹具沿用 c150/c151 的可区分样例（真机 dec 搜得）：
`hand=[9b,2w,7w,7b,1b,2w,东,1w,4w,1b,东,1b,3w,8w], drawn=8w`
  c150（无加成）弃 **1w**；c151（满额加成）弃 **2w**。
本臂按牌河长度调度：**早盘权重 0.25** ⇒ 应像 c150（弃 1w）；**中盘权重 1.0** ⇒ 应像 c151（弃 2w）。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc159 import SpeedC159, phase_weight   # noqa: E402

HAND = ["9b", "2w", "7w", "7b", "1b", "2w", "东", "1w", "4w", "1b", "东", "1b", "3w", "8w"]
DRAWN = "8w"


def _view(river_len):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(HAND), "melds": [],
            "drawn_tile": DRAWN, "river": [], "river_len": river_len, "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC159PhaseWeighted(unittest.TestCase):
    def test_weight_schedule(self):
        self.assertEqual(phase_weight(0), 0.0)
        self.assertEqual(phase_weight(11), 0.0)
        self.assertEqual(phase_weight(12), 1.0)
        self.assertEqual(phase_weight(28), 1.0)
        self.assertEqual(phase_weight(29), 1.5)

    def test_early_phase_behaves_like_c150(self):
        pol = SpeedC159()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(4)), "1w")

    def test_mid_phase_behaves_like_c151(self):
        pol = SpeedC159()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(16)), "2w")

    def test_late_phase_also_breaks_pairs(self):
        pol = SpeedC159()
        self.assertEqual(pol._pick_discard(HAND, DRAWN, 0, 0, view=_view(40)), "2w")

    def test_no_mutable_global(self):
        import sys as _s
        src = inspect.getsource(_s.modules[SpeedC159.__module__])   # 模块级（含 _pick_discard_phase）
        self.assertIn("_pair_count(rem) <= 2", src)
        self.assertIn("phase_weight", src)
        self.assertNotIn("global ROUTE_BONUS", src, "不得用可变全局（一进程跑 10 场并发会串场）")
