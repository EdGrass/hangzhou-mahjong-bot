# -*- coding: utf-8 -*-
"""C219：房内分差自适应（重基座 + 修正数据源）的回归测试。"""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from bot.speedc219 import SpeedC219
from bot.speedtugc import SpeedTUGC


class TestC219(unittest.TestCase):
    def test_registered_and_subclass(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc219", F)
        p = F["speedc219"]()
        self.assertIsInstance(p, SpeedC219)
        self.assertTrue(issubclass(SpeedC219, SpeedTUGC))          # ★ 不再继承已证伪的 c211
        self.assertAlmostEqual(p.p_conv, 0.71)                     # 基线阈值

    def test_accumulates_deltas_and_detects_lag(self):
        p = SpeedC219()
        p._seat = 0
        self.assertFalse(p.lagging())                              # 无信息 ⇒ 不触发
        p._absorb_scores([-40, 60, -10, -10])                       # 我方 −40，最高 +60 ⇒ 落后 100
        self.assertEqual(p.room_scores, [-40.0, 60.0, -10.0, -10.0])
        self.assertTrue(p.lagging())
        self.assertEqual(p.n_absorbed, 1)
        self.assertFalse(p._absorb_scores([-40, 60, -10, -10]))     # 幂等：同向量不重复累加
        self.assertEqual(p.n_absorbed, 1)
        p._absorb_scores([20, -20, 0, 0])                           # 再累加
        self.assertEqual(p.room_scores, [-20.0, 40.0, -10.0, -10.0])

    def test_not_lagging_when_close(self):
        p = SpeedC219()
        p._seat = 2
        p._absorb_scores([30, -10, -10, -10])
        self.assertFalse(p.lagging())                               # 落后 40 < LAG 100

    def test_bad_scores_are_ignored(self):
        p = SpeedC219()
        for bad in (None, [], [1, 2], "abc", [1, 2, 3, "x"]):
            self.assertFalse(p._absorb_scores(bad))
        self.assertEqual(p.room_scores, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(p.n_absorbed, 0)

    def test_guard_resets_on_overflow(self):
        p = SpeedC219()
        p._seat = 0
        for _ in range(40):
            p._absorb_scores([0, 0, 0, 0])                          # 零向量不累加
            p._absorb_scores([-100, 100, 0, 0])
        self.assertLessEqual(max(abs(x) for x in p.room_scores), p.GUARD if hasattr(p, "GUARD") else 3000.0)

    def test_decide_sets_pconv_and_counts(self):
        p = SpeedC219()
        # 用最小 view 触发 decide 的记账路径（不做实际决策：非我方回合）
        v = {"seat": 0, "phase": "draw", "turn": 1, "my_hand": [], "scores": [-120, 120, 0, 0],
             "responding_seats": [], "melds": [], "all_melds": [], "god": {}}
        p.decide(v)
        self.assertEqual(p.n_dec, 1)
        self.assertEqual(p.n_lag, 1)
        self.assertAlmostEqual(p.p_conv, 0.55)
        v2 = dict(v, scores=[-20, 20, 0, 0])
        p._seat = 0
        p.room_scores = [0.0, 0.0, 0.0, 0.0]; p._last_scores = None
        p.decide(v2)
        self.assertEqual(p.n_lag, 1)
        self.assertAlmostEqual(p.p_conv, 0.71)


if __name__ == "__main__":
    unittest.main()
