# -*- coding: utf-8 -*-
"""跨工具一致性 + 共享判据单测。

**为什么必须有**：这一轮已经抓到两次同类事故——"判据写在文档里，但没落到工具/配置里"
（ab_adopt 缺终点判据、ab_ctl 在 2 臂分支丢 bundles）。阈值分散在两个工具里是下一个同类风险，
所以这里用断言把 `ab_readout` 与 `ab_adopt` 的四个阈值钉成同一个值。
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rd = _load("rd", os.path.join("tools", "ab_readout.py"))
ad = _load("ad", os.path.join("tools", "ab_adopt.py"))


class TestCrossToolThresholds(unittest.TestCase):
    def test_thresholds_identical(self):
        self.assertEqual(rd.T_THRESHOLD, ad.T_THRESHOLD)
        self.assertEqual(rd.MIN_ROOMS, ad.MIN_ROOMS)
        self.assertEqual(rd.BUNDLE_THRESHOLD, ad.BUNDLE_THRESHOLD)
        self.assertEqual(rd.BUNDLE_ROOMS, ad.BUNDLE_ROOMS)
        self.assertEqual(rd.SINGLE_THRESHOLD, ad.SINGLE_THRESHOLD)
        self.assertEqual(rd.SINGLE_ROOMS, ad.SINGLE_ROOMS)

    def test_bundle_values_are_the_preregistered_ones(self):
        self.assertEqual((rd.BUNDLE_THRESHOLD, rd.BUNDLE_ROOMS), (1.50, 150))
        self.assertEqual((rd.SINGLE_THRESHOLD, rd.SINGLE_ROOMS), (1.96, 100))
        self.assertEqual((rd.T_THRESHOLD, rd.MIN_ROOMS), (3.0, 12))

    def test_arm_verdict_matches_adopt_verdict(self):
        """两个工具的判据必须对同一输入给同一结论。"""
        for t, na, nb, b in [(3.5, 12, 12, False), (1.7, 160, 160, True),
                             (1.7, 160, 160, False), (2.5, 120, 120, False),
                             (-3.2, 12, 12, False), (0.4, 20, 20, True),
                             (1.2, 160, 160, True),
                             # futility 区间：readout 给收尾建议，adopt 仍然一律不采用
                             (0.4, 120, 120, True), (0.0, 99, 99, False),
                             (0.7, 120, 120, True), (1.6, 120, 120, True)]:
            v, thr, end_n = rd.arm_verdict(t, na, nb, b)
            ok, rule = ad.verdict(t, na, nb, b)
            # 语义差异（有意为之，别改成"直接相等"）：
            #   rd.arm_verdict → "对**这个臂**该做什么"（drop-arm 表示它更差、不该采用）
            #   ad.verdict     → "两臂之间**是否已达到可判定差异**"（哪边更好由 main 里的 win 决定）
            # ⇒ 安全不变式（**必须是单边的**）：readout 说要采用 ⇒ adopt 也说达到判据且 t>0。
            #   反过来不成立：ad.verdict 只看阈值，readout 还额外要求跑满终点房数
            #   （见 test_adopt_beats_futility），所以 t=1.6/120 房时 adopt=True 而 readout=pending。
            if v in ("adopt-early", "adopt"):
                self.assertTrue(ok and t > 0,
                                "t=%.2f n=%d/%d bundle=%s: readout=%s adopt=%s"
                                % (t, na, nb, b, v, rule))
            # futility 绝不能与 adopt 同时成立
            if v == "futility":
                self.assertFalse(ok and t > 0)
            self.assertEqual(thr, ad.BUNDLE_THRESHOLD if b else ad.SINGLE_THRESHOLD)
            self.assertEqual(end_n, ad.BUNDLE_ROOMS if b else ad.SINGLE_ROOMS)


class TestArmVerdict(unittest.TestCase):
    def test_pending_until_end(self):
        self.assertEqual(rd.arm_verdict(2.0, 40, 40, True)[0], "pending")

    def test_bundle_end_uses_150(self):
        self.assertEqual(rd.arm_verdict(1.7, 160, 160, True)[0], "adopt")
        self.assertEqual(rd.arm_verdict(1.7, 140, 140, True)[0], "pending")

    def test_drop_arm_on_strongly_negative(self):
        self.assertEqual(rd.arm_verdict(-3.2, 20, 20, False)[0], "drop-arm")

    def test_positive_but_small_stays_baseline_at_end(self):
        self.assertEqual(rd.arm_verdict(0.8, 160, 160, True)[0], "keep-baseline")

    # ── 「无效性提前收尾」预登记规则（STATUS §4c-27）──
    def test_futility_at_100_rooms_with_tiny_effect(self):
        self.assertEqual(rd.arm_verdict(0.4, 120, 120, True)[0], "futility")
        self.assertEqual(rd.arm_verdict(-0.3, 100, 100, False)[0], "futility")

    def test_no_futility_before_room_gate(self):
        """99 房/臂不触发——差的这 1 房不构成理由，规则是硬门槛。"""
        self.assertEqual(rd.arm_verdict(0.0, 99, 99, False)[0], "pending")
        self.assertEqual(rd.arm_verdict(0.0, 120, 99, True)[0], "pending")

    def test_no_futility_just_above_t_threshold(self):
        """|t|=0.7 > 0.60 ⇒ 不触发（0.7×1.2247=0.86，仍有非平凡可能）。"""
        self.assertEqual(rd.arm_verdict(0.7, 120, 120, True)[0], "pending")
        self.assertEqual(rd.arm_verdict(-0.7, 120, 120, True)[0], "pending")

    def test_futility_gate_precedes_end_verdict(self):
        """futility 优先于终点规则（两者都判"不采用"，但前者给出可执行的收尾动作）。

        单变量：房门槛与终点同在 100 ⇒ 小效应判 futility 而不是 keep-baseline。
        组合臂：终点 150 房，但 150 房时 |t|=0.5 依然 < FUTILITY_T ⇒ 仍是 futility。
        这不是漏判——跑到 150 房都没到 0.6，说明这个束就是没有可测效应。
        """
        self.assertEqual(rd.arm_verdict(0.5, 100, 100, False)[0], "futility")
        self.assertEqual(rd.arm_verdict(0.5, 149, 149, True)[0], "futility")
        self.assertEqual(rd.arm_verdict(0.5, 150, 150, True)[0], "futility")
        # 只要 |t| >= FUTILITY_T，终点规则就接管（0.8 时是 keep-baseline）
        self.assertEqual(rd.arm_verdict(0.8, 150, 150, True)[0], "keep-baseline")

    def test_adopt_beats_futility(self):
        """正常可达标的臂不得被判 null（哨兵：防止门槛顺序写反）。

        注意 t=1.6 / 120 房时两边的组合臂 adopt 都还没成立——**采用要求跑满终点房数**
        （组合臂 150 房），t 只是进入终点判定的前提。所以 120 房是 "pending"/False，
        150 房才是 "adopt"/True。两者对"能否采用"的答案必须一致（单边不变式见上）。
        """
        self.assertEqual(rd.arm_verdict(1.6, 120, 120, True)[0], "pending")
        ok, rule = ad.verdict(1.6, 120, 120, True)
        self.assertFalse(ok)
        self.assertIsNone(rule)
        self.assertEqual(rd.arm_verdict(1.6, 150, 150, True)[0], "adopt")
        self.assertTrue(ad.verdict(1.6, 150, 150, True)[0])
        self.assertEqual(rd.arm_verdict(3.1, 12, 12, False)[0], "adopt-early")
        self.assertEqual(rd.arm_verdict(-3.1, 12, 12, False)[0], "drop-arm")

    def test_futility_verdict_is_not_silently_adopted(self):
        """readout 的 futility 绝不能让 adopt 工具跟着采用。"""
        for t in (0.0, 0.4, -0.4):
            v, _thr, _n = rd.arm_verdict(t, 120, 120, True)
            self.assertEqual(v, "futility")
            ok, rule = ad.verdict(t, 120, 120, True)
            self.assertFalse(ok)
            self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
