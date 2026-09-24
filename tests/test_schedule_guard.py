# -*- coding: utf-8 -*-
"""var/_schedule_guard.py 的单测（纯函数 + 边界）。

为什么要钉：它把"会不会赶不上 10/7"变成一条读数。本机实测：全到盒 926 房 ⇒ 收口约 10/06 17:30，
截止 10/07 08:30 ⇒ **只剩 ~15 小时余量** ⇒ 一旦它算错（例如吞吐窗口取错），排期判断就会失真。
"""
from __future__ import annotations
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _schedule_guard as G  # noqa: E402


def rows_at(start, n, step_min, arm="speedvalue"):
    return [(start + dt.timedelta(minutes=step_min * i), arm) for i in range(n)]


class TestPure(unittest.TestCase):
    def test_throughput_simple(self):
        # 每 15 分钟一房 ⇒ 4 房/小时
        r = rows_at(dt.datetime(2026, 9, 25, 0, 0), 20, 15)
        thr = G.throughput(r, hours=24)
        self.assertAlmostEqual(4.0, thr, places=2)

    def test_throughput_empty_or_single(self):
        self.assertEqual(0.0, G.throughput([], hours=24))
        self.assertEqual(0.0, G.throughput(rows_at(dt.datetime(2026, 9, 25), 1, 15), hours=24))

    def test_rooms_left_counts_per_arm(self):
        since = dt.datetime(2026, 9, 25, 0, 0, 0)
        r = rows_at(since, 50, 15, arm="speedvalue") + rows_at(since, 40, 15, arm="speedc151")
        r.sort()
        # 剩余 = 各臂缺口之和：speedvalue 缺 30、speedc151 缺 40、third 缺 80 ⇒ 150
        left = G.rooms_left(r, ["speedvalue", "speedc151", "third"], 80, since=since)
        self.assertEqual(150, left)

    def test_rooms_left_zero_when_reached(self):
        since = dt.datetime(2026, 9, 25, 0, 0, 0)
        r = rows_at(since, 100, 15, arm="speedvalue")
        self.assertEqual(0, G.rooms_left(r, ["speedvalue"], 80, since=since))

    def test_read_rows_skips_bad_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "led.jsonl")
            with io.open(p, "w", encoding="utf-8") as f:
                f.write("not json\n")
                f.write(json.dumps({"ts": "2026-09-25 01:00:00", "strategy": "speedvalue"}) + "\n")
                f.write(json.dumps({"ts": "bad", "strategy": "x"}) + "\n")
            r = G.read_rows(p)
        self.assertEqual(1, len(r))
        self.assertEqual("speedvalue", r[0][1])

    def test_arms_now_n_arm_and_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ab.json")
            with io.open(p, "w", encoding="utf-8") as f:
                f.write(json.dumps({"arms": ["a", "b", "c"]}))
            self.assertEqual(["a", "b", "c"], G.arms_now(p))
            with io.open(p, "w", encoding="utf-8") as f:
                f.write(json.dumps({"a": "x", "b": "y"}))
            self.assertEqual(["x", "y"], G.arms_now(p))


if __name__ == "__main__":
    unittest.main()
