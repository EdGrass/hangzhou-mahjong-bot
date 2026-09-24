# -*- coding: utf-8 -*-
"""`tools/ladder_snapshot.py` 的纯函数单测（快照压平 + 趋势）。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ls = _load("ladder_snapshot_t", "tools/ladder_snapshot.py")

J = {"me": {"rank": 574, "rooms": 433, "score": -7625, "firsts": 78},
     "top": [{"score": 99918}]}


class TestSnapshot(unittest.TestCase):
    def test_fields_and_per_room(self):
        r = ls.snapshot("all", J, ts="2026-09-17 02:10:00")
        self.assertEqual(r["period"], "all")
        self.assertEqual(r["rank"], 574)
        self.assertEqual(r["rooms"], 433)
        self.assertEqual(r["score"], -7625.0)
        self.assertAlmostEqual(r["score_per_room"], -7625.0 / 433, places=6)
        self.assertEqual(r["top1_score"], 99918)

    def test_zero_rooms_no_div0(self):
        r = ls.snapshot("today", {"me": {"rooms": 0, "score": 0}, "top": []})
        self.assertIsNone(r["score_per_room"])
        self.assertIsNone(r["top1_score"])

    def test_trend_computes_per_room(self):
        rows = [{"ts": "2026-09-17 01:00:00", "period": "all", "rooms": 100, "score": -1000},
                {"ts": "2026-09-17 02:00:00", "period": "all", "rooms": 110, "score": -1227},
                {"ts": "2026-09-17 03:00:00", "period": "week", "rooms": 5, "score": -50}]
        v, tr = ls.trend(rows, "all")
        self.assertEqual(len(v), 2)
        self.assertEqual(len(tr), 1)
        _, _, dr, ds, spr = tr[0]
        self.assertEqual((dr, ds), (10, -227))
        self.assertAlmostEqual(spr, -22.7, places=6)


if __name__ == "__main__":
    unittest.main()
