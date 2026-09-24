# -*- coding: utf-8 -*-
"""A/B 熔断器（_ab_driver.guard_candidate）单测。

**为什么必须单测**：2026-09-16 发现旧实现用的是**绝对阈值**（"候选近 4 房均值 < -150 就熔断"），
而房级净胜 SD ≈194 ⇒ 4 房均值 SE ≈97 ⇒ **一个与基线完全相同的候选也有约 6% 的概率被误杀**，
在上百房的战役里会累积成"噪声杀"。修法是改判**候选 − 基线**并用校准阈值（12 房 -150 ≈1.9σ）。`r`n`r`n★ 2026-09-20 再修（R699）：快档由 **4 房 -300** 改为 **6 房 -300**。用 23 段历史战役的真实交叉排批`r`n数据回放该统计量（83 次检查）：4 房档有 2 次 < -300（全在 2026-09-20，同一窗口同时命中 c151 -488 与`r`n*c191 -475*，而 c191 是机制未生效的臂）⇒ 4 房档量的是窗口不是臂；6/8/10/12 房档 **0 次**。
这些断言把新旧语义钉死，防止回退。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("_ab_drv_t", os.path.join(ROOT, "var", "_ab_driver.py"))
drv = importlib.util.module_from_spec(spec)
sys.modules["_ab_drv_t"] = drv
spec.loader.exec_module(drv)


def patch(cand_vals, base_vals):
    """把 arm_recent_net 换成可控序列（也用来验证 arm_recent 的取值口径）。"""
    def fake(strategy, since):
        return list(cand_vals if strategy == "cand" else base_vals)
    drv.arm_recent_net = fake


class TestGuard(unittest.TestCase):
    def tearDown(self):
        spec.loader.exec_module(drv)          # 还原真实实现

    def test_no_data_does_not_abort(self):
        patch([], [])
        abort, m, n, base = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertFalse(abort)
        self.assertEqual(n, 0)

    def test_real_catastrophe_aborts_fast(self):
        # 候选比基线每房差 -375 ⇒ 6 房差值 -375 < -300 ⇒ 快档熔断（R699 起快档为 6 房）
        patch([-350, -400, -450, -300, -400, -350], [0] * 6)
        abort, m, n, base = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertTrue(abort)
        self.assertEqual(n, drv.GUARD_MIN_ROOMS)
        self.assertAlmostEqual(m, -375.0)
        self.assertAlmostEqual(base, 0.0)

    def test_unlucky_absolute_but_equal_does_not_abort(self):
        """★ 回归：候选与基线**同步**大跌（房间运气差）时，旧实现会误杀，新实现必须放行。"""
        patch([-260, -280, -240, -300, -290, -270], [-250, -270, -230, -290, -280, -260])
        abort, m, n, base = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertFalse(abort, "候选−基线只有 -10/房，绝对水平再差也不该熔断")
        self.assertAlmostEqual(m, -10.0)

    def test_identical_arms_never_abort(self):
        patch([-100, 50, -20, 30, 10, -40, 0, 20, -10, 5, -5, 15],
              [-100, 50, -20, 30, 10, -40, 0, 20, -10, 5, -5, 15])
        abort, m, n, base = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertFalse(abort)
        self.assertAlmostEqual(m, 0.0)

    def test_mild_leak_aborts_only_at_12_rooms(self):
        # 前 5 房差值不小（放行快档），12 房平均差值 -170 ⇒ 慢档熔断
        cand = [-100, -100, -100, -100] + [-200] * 8
        base = [0] * 12
        # 先只给前 5 房（< 快档 6 房）⇒ 不熔断
        patch(cand[:5], base[:5])
        abort, _m, _n, _b = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertFalse(abort)
        # 给满 12 房 ⇒ 最后 12 房差值 -170 < -150 ⇒ 慢档熔断
        patch(cand, base)
        abort, m, n, _b = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertTrue(abort)
        self.assertEqual(n, drv.GUARD_MILD_ROOMS)
        self.assertAlmostEqual(m, -166.6666666, places=4)

    def test_thresholds_are_the_calibrated_ones(self):
        self.assertEqual((drv.GUARD_MIN_ROOMS, drv.GUARD_NET), (6, -300.0))
        self.assertEqual((drv.GUARD_MILD_ROOMS, drv.GUARD_MILD_NET), (12, -150.0))

    def test_missing_baseline_falls_back_without_aborting(self):
        patch([-800, -900, -700, -600], [])   # 基线没有数据
        abort, m, n, base = drv.guard_candidate("cand", "base", "2026-01-01")
        self.assertFalse(abort, "基线缺失时不能仅凭候选绝对值熔断（旧实现的病根）")
        self.assertEqual(n, 4)


if __name__ == "__main__":
    unittest.main()
