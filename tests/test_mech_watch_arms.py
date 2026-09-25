# -*- coding: utf-8 -*-
"""`var/_mech_watch.py` 的单测（R1481）。

为什么要钉：这个看护是**役内机制端点**的唯一执行者，而两份役 3 预登记都把机制定为本役核心、
并写死 B3（机制不达标 ⇒ 本役作废）。本轮发现它**只读两臂时代的 `a`/`b` 字段**，
对三臂的 `.ab_mode`（`arms` 列表）会 `arms=[None,None]` ⇒ **静默 no-op** ⇒ 整个机制守护等于没跑。
另钉住 V 轴机制（campaign7 §2：**爆头/胡 上升 且 番/胡 上升**）的表格解析与判据。
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _mech_watch as M  # noqa: E402


H2H = u"""同房头对头（本役 120 房；唯一 gid 9600）
============================================================================================================================================
speedvalue 我方              局    960 | 胡/轮 25.11% | 番/胡 1.290 | 分/轮   +0.03 | 赢   +5.11 输   -4.98 | 爆头/胡  22.4% 财飘 11.0% 杠开 0.10 | 副露/轮 3.100 杠/轮 0.060(明0.040补0.010暗0.010)
speedvalue 另三家              局   2880 | 胡/轮 24.00% | 番/胡 1.250 | 分/轮   -0.01 | 赢   +4.90 输   -5.02 | 爆头/胡  21.0% 财飘 10.0% 杠开 0.09 | 副露/轮 3.000 杠/轮 0.059(明0.039补0.009暗0.011)
speedvaluebaotouv5 我方        局    960 | 胡/轮 24.80% | 番/胡 1.350 | 分/轮   +0.15 | 赢   +5.60 输   -5.10 | 爆头/胡  26.9% 财飘 11.2% 杠开 0.11 | 副露/轮 3.200 杠/轮 0.061(明0.041补0.010暗0.010)
speedvaluebaotouv5 另三家     局   2880 | 胡/轮 24.10% | 番/胡 1.260 | 分/轮   -0.02 | 赢   +4.95 输   -5.00 | 爆头/胡  21.2% 财飘 10.1% 杠开 0.09 | 副露/轮 3.010 杠/轮 0.058(明0.038补0.009暗0.011)
"""


class TestArmsOf(unittest.TestCase):
    def test_n_arm_format(self):
        cfg = {"arms": ["speedvalue", "speedvaluebc", "speedvaluebaotouv5"],
               "bundles": ["speedvalue"]}
        self.assertEqual(3, len(M.arms_of(cfg)))
        self.assertEqual("speedvaluebc", M.arms_of(cfg)[1])

    def test_legacy_two_arm_format(self):
        self.assertEqual(["x", "y"], M.arms_of({"a": "x", "b": "y"}))

    def test_empty(self):
        self.assertEqual([], M.arms_of({}))


class TestUnkAction(unittest.TestCase):
    """R1484\uff1a`.v_mech_unknown` \u7684\u5199/\u5220\u7b56\u7565\u2014\u2014 **\u8bfb\u6570\u9f50\u4e86\u5fc5\u987b\u6e05\u6807\u8bb0**\u3002"""

    def test_no_v_candidates_clears(self):
        self.assertEqual("clear", M.unk_action([], []))

    def test_all_judged_clears_even_if_failed(self):
        # \u5224\u4e0d\u8fbe\u6807\u8d70 .mech_warn\uff1b\u201c\u65e0\u6cd5\u5224\u201d\u90a3\u4e2a\u6807\u8bb0\u5c31\u4e0d\u80fd\u7559\u7740
        self.assertEqual("clear", M.unk_action(["v"], [True]))
        self.assertEqual("clear", M.unk_action(["v"], [False]))

    def test_any_unknown_writes(self):
        self.assertEqual("write", M.unk_action(["v"], [None]))
        self.assertEqual("write", M.unk_action(["v1", "v2"], [True, None]))


class TestParseH2H(unittest.TestCase):
    def test_extracts_both_arms_and_sides(self):
        rows = M.parse_h2h(H2H)
        self.assertEqual(4, len(rows))
        me = rows[("speedvalue", "我方")]
        self.assertAlmostEqual(25.11, me["hu"], places=2)
        self.assertAlmostEqual(1.29, me["fan"], places=2)
        self.assertAlmostEqual(22.4, me["baotou"], places=1)
        cand = rows[("speedvaluebaotouv5", "我方")]
        self.assertAlmostEqual(1.35, cand["fan"], places=2)
        self.assertAlmostEqual(26.9, cand["baotou"], places=1)

    def test_garbage_and_header_ignored(self):
        self.assertEqual({}, M.parse_h2h(""))
        self.assertEqual({}, M.parse_h2h(u"没有表头的一行\n另一行"))


class TestJudgeVMech(unittest.TestCase):
    BASE = {"baotou": 22.4, "fan": 1.29, "hu": 25.11, "rounds": 960}

    def test_both_up_is_pass(self):
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": 24.8, "rounds": 960})
        self.assertTrue(ok, why)

    def test_only_baotou_up_is_fail(self):
        # 只升爆头不升番/胡 = 只把命中换成了爆头标签，没把牌打大
        ok, _ = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.20, "hu": 25.0, "rounds": 960})
        self.assertFalse(ok)

    def test_only_fan_up_is_fail(self):
        ok, _ = M.judge_v_mech(self.BASE, {"baotou": 21.0, "fan": 1.40, "hu": 25.0, "rounds": 960})
        self.assertFalse(ok)

    def test_small_sample_is_not_judged(self):
        # ★ R1481：局数不够就**不判**（否则 2 房的噪声会被当成 B3，把好臂挂掉）
        ok, why = M.judge_v_mech({"baotou": 22.4, "fan": 1.29, "rounds": 40},
                                 {"baotou": 26.9, "fan": 1.35, "rounds": 40})
        self.assertIsNone(ok, why)
        self.assertIn(u"样本不足", why)

    def test_parse_extracts_rounds(self):
        rows = M.parse_h2h(H2H)
        self.assertEqual(960, rows[("speedvalue", u"我方")]["rounds"])
        self.assertEqual(2880, rows[("speedvalue", u"另三家")]["rounds"])

    def test_missing_readings_is_none(self):
        ok, why = M.judge_v_mech(self.BASE, None)
        self.assertIsNone(ok, why)
        ok2, _ = M.judge_v_mech(None, self.BASE)
        self.assertIsNone(ok2)
        ok3, _ = M.judge_v_mech(self.BASE, {"baotou": None, "fan": 1.4, "rounds": 960})
        self.assertIsNone(ok3)


if __name__ == "__main__":
    unittest.main()
