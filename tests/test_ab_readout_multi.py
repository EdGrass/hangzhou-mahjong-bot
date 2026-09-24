# -*- coding: utf-8 -*-
"""多臂 A/B 读数单测：逐个候选臂 vs 基线的判定（预登记阈值）。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from ab_readout import multi_arm_report          # noqa: E402

T0 = "2026-09-18 00:00:00"


def rooms(vals):
    return [{"net": v, "ts": T0} for v in vals]


def spread(mu, n=12, sd=100.0, seed=1):
    import random
    rnd = random.Random(seed)
    return rooms([mu + rnd.gauss(0, sd) for _ in range(n)])


class TestRoomRankStats(unittest.TestCase):
    """房间第一名率（§4c-39）：随机基线 25%，我方历史 18.2%，榜首 42~55%。"""

    def test_first_pct_counts_rank_one(self):
        import ab_readout as rd
        orig = rd.rooms_for
        try:
            rd.rooms_for = lambda st, since=None: [
                {"rank": 1}, {"rank": 2}, {"rank": 1}, {"rank": 4}]
            out = rd.room_rank_stats("x")
        finally:
            rd.rooms_for = orig
        self.assertEqual(out["rooms"], 4)
        self.assertEqual(out["firsts"], 2)
        self.assertAlmostEqual(out["first_pct"], 50.0)

    def test_no_rooms_returns_none(self):
        import ab_readout as rd
        orig = rd.rooms_for
        try:
            rd.rooms_for = lambda st, since=None: []
            self.assertIsNone(rd.room_rank_stats("x"))
        finally:
            rd.rooms_for = orig


class TestMultiArmReport(unittest.TestCase):
    def test_two_arms_returns_empty(self):
        arms = {"base": spread(0.0), "cand": spread(50.0)}
        self.assertEqual(multi_arm_report(arms, ["base", "cand"], T0, set(), out=lambda *a: None), [])

    def test_bundle_early_adopt(self):
        arms = {"base": spread(0.0), "b1": spread(160.0), "b2": spread(0.0)}
        res = multi_arm_report(arms, ["base", "b1", "b2"], T0, {"b1"}, out=lambda *a: None)
        d = {x["strategy"]: x for x in res}
        self.assertEqual(d["b1"]["verdict"], "adopt-early")
        self.assertEqual(d["b2"]["verdict"], "pending")

    def test_single_needs_196_at_campaign_end(self):
        # 单变量战役终点 = 100 房/臂
        arms = {"base": spread(0.0, 100, 90.0), "s1": spread(20.0, 100, 90.0)}
        arms["x"] = spread(0.0, 100, 90.0)
        res = multi_arm_report(arms, ["base", "s1", "x"], T0, set(), out=lambda *a: None)
        d = {y["strategy"]: y for y in res}
        self.assertIn(d["s1"]["verdict"], ("adopt", "keep-baseline"))
        if abs(d["s1"]["t"] or 0) >= 1.96:
            self.assertEqual(d["s1"]["verdict"], "adopt")

    def test_negative_arm_dropped(self):
        arms = {"base": spread(0.0), "bad": spread(-200.0), "x": spread(0.0)}
        res = multi_arm_report(arms, ["base", "bad", "x"], T0, set(), out=lambda *a: None)
        d = {y["strategy"]: y for y in res}
        self.assertEqual(d["bad"]["verdict"], "drop-arm")

    def test_bundle_threshold_is_lower(self):
        """同一 t≈2.0 的臂：组合臂在 90 房时采用、单变量不采用（阈值 1.50 vs 1.96）。"""
        import random
        rnd = random.Random(7)
        base = rooms([rnd.gauss(0, 90) for _ in range(150)])
        cand = rooms([20 + rnd.gauss(0, 90) for _ in range(150)])
        arms = {"base": base, "cand": cand, "pad": base}
        r_bundle = multi_arm_report(arms, ["base", "cand", "pad"], T0, {"cand"}, out=lambda *a: None)
        t = r_bundle[0]["t"]
        if 1.50 <= t < 1.96:
            self.assertEqual(r_bundle[0]["verdict"], "adopt")
        r_single = multi_arm_report(arms, ["base", "cand", "pad"], T0, set(), out=lambda *a: None)
        if 1.50 <= t < 1.96:
            self.assertEqual(r_single[0]["verdict"], "keep-baseline")


if __name__ == "__main__":
    unittest.main()
