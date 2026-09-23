# -*- coding: utf-8 -*-
"""对手强度/桌强调整的单元测试（因果性 + 斜率）。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import opp_strength as oa        # noqa: E402

ME = oa.ME


def row(ts, room, opps, mine=0.0):
    """opps = [(uid, score), ...]"""
    rk = [{"user_id": ME, "total_score": mine, "rank": 1}]
    for i, (uid, sc) in enumerate(opps):
        rk.append({"user_id": uid, "total_score": sc, "rank": i + 2})
    return {"ts": ts, "room": room, "strategy": "t", "status": "finished", "ranking": rk}


class TestOpponentStrength(unittest.TestCase):
    def test_uses_only_prior_rooms_and_min_rooms(self):
        rows = []
        # u0：9 个先行房，每房 +100 ⇒ 到 rX 时已有 9 房历史 ⇒ 可估；u1：只有 2 房 ⇒ 必须被排除
        for i in range(9):
            opps = [("u0", 100.0), ("u9", 0.0)] + ([("u1", 5.0)] if i < 2 else [])
            rows.append(row("2026-09-15 %02d:00:00" % i, "r%d" % i, opps))
        rows.append(row("2026-09-16 10:00:00", "rX", [("u0", 100.0), ("u1", 5.0)]))
        opp = oa.opponent_strength(rows)
        self.assertNotIn("r0", opp, "第一房之前没有历史 ⇒ 无法估计")
        self.assertIn("rX", opp)
        self.assertAlmostEqual(opp["rX"], 100.0, places=6,
                               msg="强度必须只用该房之前的历史，且 <8 房的对手（u1）被排除")

    def test_strength_is_causal_not_lookahead(self):
        rows = [row("2026-09-15 10:00:00", "r1", [("u0", 500.0)])]
        for i in range(8):
            rows.append(row("2026-09-15 11:0%d:00" % i, "m%d" % i, [("u0", 0.0)]))
        rows.append(row("2026-09-16 09:00:00", "rLate", [("u0", 0.0)]))
        opp = oa.opponent_strength(rows)
        self.assertNotIn("r1", opp)
        # u0 在 rLate 之前的历史：1×+500 + 8×0 = 9 房 ⇒ 均值 55.56（不能把 rLate 自己算进去）
        self.assertAlmostEqual(opp["rLate"], 500.0 / 9, places=4)

    def test_slope(self):
        self.assertAlmostEqual(oa.slope([0, 1, 2, 3], [0, -10, -20, -30]), -10.0, places=6)
        self.assertEqual(oa.slope([1, 2], [1, 2]), 0.0, msg="样本 <3 ⇒ 斜率 0")
