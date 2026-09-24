# -*- coding: utf-8 -*-
"""分层读数工具的单测（`_strong_slice` / `_strong_veto` / `_adopt_when_ready.adopted_arm`）。

为什么要钉：
1. `_adopt_when_ready.adopted_arm` 是本轮的**真 bug** —— 判词是
   `ADOPT speedvalue（和牌率 z=+1.80、番 z=+1.60、护栏通过）`，括号前有空格 ⇒
   `split()[1]` 取到 `speedvalue（和牌率`，否决闸于是去查一个**不存在的臂**（0 房）；
2. `_strong_veto.veto_of` 是"该轴要不要被否决"的唯一判据（§V.156 + 役 3 预登记）；
3. `_strong_slice` 的分类必须与 `_verdict_by_elite` 的台账口径一致
   （本机实测：105 强 / 46 弱，与 53+52 / 22+24 完全对上）。
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _strong_slice as SS  # noqa: E402
import _strong_veto as SV  # noqa: E402
import _adopt_when_ready as AW  # noqa: E402


def write(path, obj):
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj))
    return path


class TestAdoptedArm(unittest.TestCase):
    def test_real_verdict_format(self):
        # 真实的 _gate2 格式（括号前有空格、括号内还有空格）
        self.assertEqual("speedvalue", AW.adopted_arm("ADOPT speedvalue（和牌率 z=+1.80、番 z=+1.60、护栏通过）"))
        self.assertEqual("speedvaluebc", AW.adopted_arm("ADOPT speedvaluebc（和牌率 z=+1.51、番 z=+1.52、护栏通过）"))

    def test_not_adopt_is_empty(self):
        for t in ("REFUSE / CONTINUE —— 第一率护栏未过", "REJECT speedvalue（和牌率 z=-2.1）",
                  "UNDECIDED（和牌率 z=+0.9）⇒ 继续攒房", ""):
            self.assertEqual("", AW.adopted_arm(t), t)

    def test_split_would_have_been_wrong(self):
        """把当年的错法固化成反例：split()[1] 一定取错。"""
        line = "ADOPT speedvalue（和牌率 z=+1.80、番 z=+1.60、护栏通过）"
        self.assertNotEqual(line.split()[1], AW.adopted_arm(line))
        self.assertEqual("speedvalue（和牌率", line.split()[1])


class TestVetoOf(unittest.TestCase):
    def test_net_only(self):
        self.assertEqual(["净分/房"], SV.veto_of(-1.97, 0.0))

    def test_first_rate_only(self):
        self.assertEqual(["第1率"], SV.veto_of(0.5, -2.5))

    def test_both(self):
        self.assertEqual(["净分/房", "第1率"], SV.veto_of(-3.0, -4.0))

    def test_none(self):
        self.assertEqual([], SV.veto_of(-0.50, -0.67))
        self.assertEqual([], SV.veto_of(-1.95, -1.95))

    def test_none_inputs_are_ignored(self):
        self.assertEqual([], SV.veto_of(None, None))

    def test_boundary_is_inclusive(self):
        self.assertEqual(["净分/房"], SV.veto_of(-1.96, 0.0))


class TestStats(unittest.TestCase):
    def test_welch_positive_when_candidate_bigger(self):
        a = [0.0, 1.0, 2.0, 3.0]
        b = [10.0, 11.0, 12.0, 13.0]
        d, se, z = SV._welch(a, b)
        self.assertAlmostEqual(10.0, d)
        self.assertGreater(z, 5)

    def test_welch_none_when_too_few(self):
        self.assertIsNone(SV._welch([1.0], [2.0, 3.0]))

    def test_prop_z_sign(self):
        # 语义 = 候选 − 基线（与 _welch 一致）
        dp, zp = SV._prop_z(9, 20, 1, 20)      # 基线 45% vs 候选 5% ⇒ 候选更差
        self.assertAlmostEqual(-0.40, dp, places=6)
        self.assertLess(zp, -2)
        dp2, zp2 = SV._prop_z(1, 20, 9, 20)    # 基线 5% vs 候选 45% ⇒ 候选更好
        self.assertGreater(dp2, 0)
        self.assertGreater(zp2, 2)


class TestSlicePure(unittest.TestCase):
    def test_room_of(self):
        self.assertEqual("a_001aa095219e", SS.room_of("a_001aa095219e_r1_b0_t0.json"))
        self.assertIsNone(SS.room_of("nonsense.json"))

    def test_ledger_rooms_filters_by_ts(self):
        with tempfile.TemporaryDirectory() as d:
            led = os.path.join(d, "led.jsonl")
            with io.open(led, "w", encoding="utf-8") as f:
                f.write(json.dumps({"ts": "2026-09-23 01:00:00", "room": "a_aaa"}) + "\n")
                f.write(json.dumps({"ts": "2026-09-23 04:00:00", "room": "a_bbb"}) + "\n")
                f.write(json.dumps({"ts": "2026-09-23 05:00:00"}) + "\n")
            # 它读模块常量 LEDGER ⇒ 临时替换成临时台账
            old = SS.LEDGER
            try:
                SS.LEDGER = led
                self.assertEqual({"a_bbb"}, SS.ledger_rooms("2026-09-23 03:00:00"))
            finally:
                SS.LEDGER = old

    def test_classify(self):
        with tempfile.TemporaryDirectory() as d:
            top = {"u_top1"}
            p = write(os.path.join(d, "a_000000000001_r1_b0_t0.json"),
                      {"seats": [{"user_id": SS.ME}, {"user_id": "u_top1"},
                                 {"user_id": "u_x"}, {"user_id": "u_y"}]})
            self.assertEqual((True, True), SS.classify(p, top))
            p2 = write(os.path.join(d, "a_000000000002_r1_b0_t0.json"),
                       {"seats": [{"user_id": SS.ME}, {"user_id": "u_x"},
                                  {"user_id": "u_y"}, {"user_id": "u_z"}]})
            self.assertEqual((True, False), SS.classify(p2, top))
            p3 = write(os.path.join(d, "a_000000000003_r1_b0_t0.json"),
                       {"seats": [{"user_id": "u_top1"}, {"user_id": "u_x"},
                                  {"user_id": "u_y"}, {"user_id": "u_z"}]})
            self.assertIsNone(SS.classify(p3, top))     # 没有我方 ⇒ 跳过

    def test_board_top_missing_cookie_fails_loud(self):
        """榜单拿不到必须**抛**（main 会退 2）——绝不用空榜切出'假强手房'。"""
        old = SS.COOKIE
        try:
            SS.COOKIE = os.path.join(os.path.dirname(old), "_no_such_cookie_file")
            with self.assertRaises(Exception):
                SS.board_top(32)
        finally:
            SS.COOKIE = old


if __name__ == "__main__":
    unittest.main()
