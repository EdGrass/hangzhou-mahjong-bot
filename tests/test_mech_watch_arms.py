# -*- coding: utf-8 -*-
"""`var/_mech_watch.py` 的单测（R1481）。

为什么要钉：这个看护是**役内机制端点**的唯一执行者，而两份役 3 预登记都把机制定为本役核心、
并写死 B3（机制不达标 ⇒ 本役作废）。本轮发现它**只读两臂时代的 `a`/`b` 字段**，
对三臂的 `.ab_mode`（`arms` 列表）会 `arms=[None,None]` ⇒ **静默 no-op** ⇒ 整个机制守护等于没跑。
另钉住 V 轴机制（campaign7 §2：**爆头/胡 上升 且 番/胡 上升**）的表格解析与判据。
"""
from __future__ import annotations
import io
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


class TestParseH2HCompatR1501(unittest.TestCase):
    """★ R1509：`_seat_h2h` 在 R1501 之后会多打 `vs TOPn` / `vs 非TOP` 两类行。

    这些行**不是**“臂 + 我方/另三家”口径 ⇒ 解析必须丢弃它们（宁可缺读数，不拼假的），
    且不能因此把 `我方` / `另三家` 两行弄丢。这里用真实输出形状钉住。
    """

    SAMPLE = (
        "speedvaluebc \u6211\u65b9         \u5c40    400 | \u80e1/\u8f6e 29.75% | \u756a/\u80e1 1.45 | \u5206/\u8f6e   +2.40 | "
        "\u8d62   +6.68 \u8f93   -4.28 | \u7206\u5934/\u80e1  27.7% \u8d22\u98d8  1.7% \u6760\u5f00 2.52% | "
        "\u526f\u9732/\u8f6e 0.330 \u6760/\u8f6e 0.018(\u660e0.007\u88650.010\u66970.000)\n"
        "speedvaluebc \u53e6\u4e09\u5bb6        \u5c40   1200 | \u80e1/\u8f6e 22.08% | \u756a/\u80e1 1.33 | \u5206/\u8f6e   -0.80 | "
        "\u8d62   +4.27 \u8f93   -5.07 | \u7206\u5934/\u80e1  23.8% \u8d22\u98d8  1.5% \u6760\u5f00 1.89% | "
        "\u526f\u9732/\u8f6e 0.315 \u6760/\u8f6e 0.020(\u660e0.009\u88650.008\u66970.003)\n"
        "speedvaluebc vs TOP32   \u5c40    400 | \u80e1/\u8f6e 26.50% | \u756a/\u80e1 1.42 | \u5206/\u8f6e   +0.45 | "
        "\u8d62   +5.36 \u8f93   -4.91 | \u7206\u5934/\u80e1  30.2% \u8d22\u98d8  0.9% \u6760\u5f00 2.83% | "
        "\u526f\u9732/\u8f6e 0.398 \u6760/\u8f6e 0.020(\u660e0.007\u88650.013\u66970.000)\n"
        "speedvaluebc vs \u975eTOP    \u5c40    800 | \u80e1/\u8f6e 19.88% | \u756a/\u80e1 1.28 | \u5206/\u8f6e   -1.43 | "
        "\u8d62   +3.73 \u8f93   -5.16 | \u7206\u5934/\u80e1  19.5% \u8d22\u98d8  1.9% \u6760\u5f00 1.26% | "
        "\u526f\u9732/\u8f6e 0.274 \u6760/\u8f6e 0.020(\u660e0.010\u88650.006\u66970.004)\n"
    )

    def test_vs_top_rows_are_ignored_and_me_rows_survive(self):
        rows = M.parse_h2h(self.SAMPLE)
        self.assertEqual({("speedvaluebc", "\u6211\u65b9"), ("speedvaluebc", "\u53e6\u4e09\u5bb6")}, set(rows))
        self.assertAlmostEqual(29.75, rows[("speedvaluebc", "\u6211\u65b9")]["hu"], places=2)
        self.assertAlmostEqual(1.45, rows[("speedvaluebc", "\u6211\u65b9")]["fan"], places=2)
        self.assertAlmostEqual(23.8, rows[("speedvaluebc", "\u53e6\u4e09\u5bb6")]["baotou"], places=1)
        self.assertEqual(1200, rows[("speedvaluebc", "\u53e6\u4e09\u5bb6")]["rounds"])

    def test_empty_parse_leaves_diagnostic(self):
        """★ R1509：解析为空时必须留 rc/stderr/长度（否则“读数缺失”无法诊断）。"""
        src = io.open(os.path.join(ROOT, "var", "_mech_watch.py"), encoding="utf-8").read()
        self.assertIn("\u89e3\u6790\u4e3a\u7a7a", src)
        self.assertIn("stderr=", src)
        self.assertIn("stdout=%d", src)


class TestJudgeVMech(unittest.TestCase):
    """★ R1520：机制口径 = 预登记原文的「**爆头/胡 与 赢分/胡 两者均上升**」。

    旧实现用的是**番/胡**（不是预登记的那个量）—— 本类用“番/胡 下降但赢分/胡 上升 ⇒ PASS”这种打脸用例钉住。
    赢分/胡 = （赢（分/轮））÷（胡率/100）。
    """
    # win/hu = 4.67 / 0.2511 = 18.6 分/胡
    BASE = {"baotou": 22.4, "fan": 1.29, "hu": 25.11, "win": 4.67, "rounds": 4000}

    def test_both_up_is_pass(self):
        # 爆头 22.4→26.9；赢分/胡 18.6→21.4
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": 24.8,
                                            "win": 5.30, "rounds": 4000})
        self.assertTrue(ok, why)

    def test_fan_down_but_win_per_hu_up_is_pass(self):
        """★ 预登记里番/胡**不是**机制的第二项 ⇒ 它下降不能当不达标。"""
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.20, "hu": 24.8,
                                            "win": 5.30, "rounds": 4000})
        self.assertTrue(ok, why)

    def test_only_baotou_up_is_fail(self):
        # 爆头升但赢分/胡反而降 = 只把命中换成了爆头标签，没把牌打大
        ok, _ = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.20, "hu": 25.0,
                                          "win": 4.40, "rounds": 4000})
        self.assertFalse(ok)

    def test_fan_up_but_baotou_flat_is_fail(self):
        ok, _ = M.judge_v_mech(self.BASE, {"baotou": 21.0, "fan": 1.40, "hu": 25.0,
                                          "win": 5.00, "rounds": 4000})
        self.assertFalse(ok)

    def test_hu_guardrail_beyond_1sigma_is_fail(self):
        """★ R1517：预登记护栏“胡率不得低于基线 1σ”必须有人执行。"""
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": 22.0,
                                            "win": 4.80, "rounds": 4000})
        self.assertFalse(ok, why)
        self.assertIn("护栏未过", why)

    def test_hu_guardrail_within_1sigma_is_pass(self):
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": 24.6,
                                            "win": 5.20, "rounds": 4000})
        self.assertTrue(ok, why)

    def test_hu_guardrail_missing_reading_is_unknown(self):
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": None,
                                            "win": 5.0, "rounds": 4000})
        self.assertIsNone(ok, why)
        self.assertIn("胡率读数缺失", why)

    def test_win_reading_missing_is_unknown(self):
        """机制的第二项（赢分/胡）缺失 ⇒ 不判（不猜）。"""
        ok, why = M.judge_v_mech(self.BASE, {"baotou": 26.9, "fan": 1.35, "hu": 25.0,
                                            "win": None, "rounds": 4000})
        self.assertIsNone(ok, why)
        self.assertIn("赢分/胡", why)

    def test_gate_is_about_40_rooms_not_4(self):
        """★ R1521：门槛是**约 40 房**（80 局/房 ⇒ 3200 局），不是 4 房。

        R1481 误把局/房当成 8 ⇒ 写成 320 局（=约 4 房）⇒ 机制闸提前 10 倍点火。
        """
        self.assertEqual(3200, M.V_MECH_MIN_ROUNDS)
        # 12 房（960 局）不判——这正是修前会被判的区间
        ok, why = M.judge_v_mech({"baotou": 22.4, "fan": 1.29, "hu": 25.0, "win": 4.67, "rounds": 960},
                                 {"baotou": 26.9, "fan": 1.35, "hu": 25.0, "win": 5.0, "rounds": 960})
        self.assertIsNone(ok, why)
        self.assertIn(u"样本不足", why)

    def test_small_sample_is_not_judged(self):
        # ★ R1481：局数不够就不判（否则 2 房的噪声会被当成 B3，把好臂挂掉）
        ok, why = M.judge_v_mech({"baotou": 22.4, "fan": 1.29, "hu": 25.0, "win": 4.6, "rounds": 40},
                                 {"baotou": 26.9, "fan": 1.35, "hu": 25.0, "win": 5.0, "rounds": 40})
        self.assertIsNone(ok, why)
        self.assertIn(u"样本不足", why)

    def test_parse_extracts_rounds(self):
        rows = M.parse_h2h(H2H)
        self.assertEqual(960, rows[("speedvalue", u"我方")]["rounds"])
        self.assertEqual(2880, rows[("speedvalue", u"另三家")]["rounds"])
        self.assertAlmostEqual(5.11, rows[("speedvalue", u"我方")]["win"], places=2)

    def test_missing_readings_is_none(self):
        ok, why = M.judge_v_mech(self.BASE, None)
        self.assertIsNone(ok, why)
        ok2, _ = M.judge_v_mech(None, self.BASE)
        self.assertIsNone(ok2)
        ok3, _ = M.judge_v_mech(self.BASE, {"baotou": None, "fan": 1.4, "rounds": 960})
        self.assertIsNone(ok3)


if __name__ == "__main__":
    unittest.main()
