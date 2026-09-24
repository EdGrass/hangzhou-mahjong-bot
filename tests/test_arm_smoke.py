# -*- coding: utf-8 -*-
"""`tools/arm_smoke.py` 的纯函数单测（冒烟测试的夹具/视图口径）。

口径（与 `tools/offline_replay.to_view` 一致，已被 `var/_recon_ruler_check.py` 的尺子检验认可）：
dec 记录在 `p=draw` 时 `h` **含刚摸牌** ⇒ `my_hand` 必须原样传 `h`，同时给 `drawn_tile`。
"""
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


sm = _load("arm_smoke_t", "tools/arm_smoke.py")


class TestArmSmokeView(unittest.TestCase):
    REC = {"s": 2, "p": "draw", "t": 1, "h": ["1w"] * 14, "d": "3b",
           "o": "", "r": ["5t"], "m": [{"type": "peng", "tile": "9b"}]}

    def test_view_keeps_drawn_tile_in_hand(self):
        v = sm.to_view(self.REC)
        self.assertEqual(len(v["my_hand"]), 14, "draw 相位 my_hand 必须含刚摸牌（14-3e-g）")
        self.assertEqual(v["drawn_tile"], "3b")
        self.assertEqual(v["river_len"], 1)
        self.assertEqual(v["phase"], "draw")

    def test_view_fields_for_window(self):
        rec = dict(self.REC, p="response_peng", o="9t", d="")
        v = sm.to_view(rec)
        self.assertEqual(v["offer_tile"], "9t")
        self.assertTrue(str(v["phase"]).startswith("response_"))

    def test_window_has_responding_seats(self):
        rec = dict(self.REC, p="response_peng", o="9t", d="")
        v = sm.to_view(rec)
        self.assertEqual(v["responding_seats"], [2], "response 相位必须让 window_pending 能识别本人")

    def test_list_melds_normalized(self):
        rec = dict(self.REC, m=[["chi", "4w"]])
        v = sm.to_view(rec)
        self.assertEqual(v["melds"][0]["type"], "chi")
        self.assertEqual(v["melds"][0]["tile"], "4w")

    def test_dict_melds_preserved(self):
        v = sm.to_view(self.REC)
        self.assertEqual(v["melds"][0]["type"], "peng")

    def test_fixtures_are_real_records(self):
        fx = sm.fixtures(5, "draw")
        self.assertGreater(len(fx), 0, "应能从真机 dec 里取到夹具")
        for r in fx:
            self.assertEqual(r.get("p"), "draw")
            self.assertTrue(r.get("d"))
            self.assertGreaterEqual(len(r.get("h") or []), 13)


if __name__ == "__main__":
    unittest.main()
