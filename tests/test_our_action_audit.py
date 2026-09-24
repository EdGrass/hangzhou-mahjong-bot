# -*- coding: utf-8 -*-
"""our_action_audit 单测：本地决策流的逐席口径统计（我方动作计数）。"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("oaa", os.path.join(ROOT, "tools", "our_action_audit.py"))
oaa = importlib.util.module_from_spec(spec)
sys.modules["oaa"] = oaa
spec.loader.exec_module(oaa)


def _write(d, rows):
    p = os.path.join(d, "x.dec.jsonl")
    with io.open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


class TestScanRoomDir(unittest.TestCase):
    def test_counts_our_actions(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, [
                {"p": "draw", "a": None},
                {"p": "response_peng", "a": {"action": "peng", "tile": "1w"}},
                {"p": "response_peng", "a": {"action": "pass", "tile": ""}},
                {"p": "draw", "a": {"action": "discard", "tile": "9t"}},
                {"p": "response_chi", "a": {"action": "gang", "tile": "2w"}},
                {"p": "response_chi", "a": {"action": "hu", "tile": ""}},
            ])
            c = oaa.scan_room_dir(d)
            self.assertEqual(c["draws"], 2)          # 摸牌数 = 轮的口径
            self.assertEqual(c["act_gang"], 1)
            self.assertEqual(c["act_peng"], 1)
            self.assertEqual(c["act_pass"], 1)
            self.assertEqual(c["act_discard"], 1)
            self.assertEqual(c["act_hu"], 1)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            c = oaa.scan_room_dir(d)
            self.assertEqual(c["records"], 0)

    def test_tolerates_bad_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "y.dec.jsonl")
            with io.open(p, "w", encoding="utf-8") as f:
                f.write("not json\n")
                f.write(json.dumps({"p": "draw"}) + "\n")
            c = oaa.scan_room_dir(d)
            self.assertEqual(c["draws"], 1)


class TestStrategyOf(unittest.TestCase):
    def test_prefers_room_id_match(self):
        by_room = {"a_abc": "speedc150"}
        rows = [("2026-09-16 14:25:34", "speedtugc", "a_other")]
        self.assertEqual(oaa.strategy_of("auto_20260916_142547", "a_abc", by_room, rows), "speedc150")

    def test_falls_back_to_nearest_timestamp(self):
        by_room = {}
        rows = [("2026-09-16 14:25:34", "speedtugc", "a_x")]
        self.assertEqual(oaa.strategy_of("auto_20260916_141211", "a_unknown", by_room, rows), "speedtugc")

    def test_no_match_returns_none(self):
        self.assertIsNone(oaa.strategy_of("auto_20260916_141211", "", {}, []))


if __name__ == "__main__":
    unittest.main()
