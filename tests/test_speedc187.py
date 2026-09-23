# -*- coding: utf-8 -*-
"""speedc187（有硬时限的精确 c151）单测：
- deadline 是**可选参数**，不传时逐位保持原精确实现；
- deadline 过期时返回 (None, None)，调用者必须回退基线；
- 预算充足时与 c151 决策一致，过期时严格回退基线；
- 策略已注册，且不引入模块级可变预算。
"""
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import SpeedC151, _pick_discard_route              # noqa: E402
from bot.speedc187 import SpeedC187, BUDGET_MS                        # noqa: E402
from bot.speedt import _best_discard_t                                # noqa: E402
from bot.ukeire import real_ukeire, real_ukeire_reference             # noqa: E402


H1 = ["1w", "2w", "3w", "5w", "6w", "7w", "9w", "9w", "2t", "3t", "4t", "东", "南", "西"]
H2 = ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "南", "西"]
H3 = ["1t", "1t", "1t", "2t", "2t", "3t", "3t", "4t", "4t", "5t", "5t", "白", "白", "中"]


class TestDeadlineAPI(unittest.TestCase):
    def test_deadline_is_optional_and_exact(self):
        self.assertEqual(real_ukeire(list(H2[:13])),
                         real_ukeire_reference(list(H2[:13])))

    def test_expired_deadline_is_unavailable(self):
        self.assertEqual(real_ukeire(list(H2[:13]), deadline=time.monotonic() - 1.0),
                         (None, None))


class TestBudgetedRoute(unittest.TestCase):
    def test_expired_route_returns_fallback(self):
        base = _best_discard_t(list(H1), "西", 0, 0, god_meld=True)
        got = _pick_discard_route(list(H1), "西", 0, 0,
                                  deadline=time.monotonic() - 1.0,
                                  fallback=base)
        self.assertEqual(got, base)

    def test_zero_budget_strategy_falls_back_to_baseline(self):
        base = _best_discard_t(list(H3), "中", 0, 0, god_meld=True)
        pol = SpeedC187(budget_ms=0.0)
        self.assertEqual(pol._pick_discard(list(H3), "中", 0, 0, view=None), base)

    def test_generous_budget_matches_c151(self):
        for hand, drawn in ((H1, "西"), (H2, "西"), (H3, "中")):
            old = SpeedC151()._pick_discard(list(hand), drawn, 0, 0, view=None)
            new = SpeedC187(budget_ms=10000.0)._pick_discard(list(hand), drawn, 0, 0, view=None)
            self.assertEqual(new, old, "预算充足时 c187 必须与 c151 完全同决策")


class TestWiring(unittest.TestCase):
    def test_budget_constant_is_small_but_nonzero(self):
        self.assertGreater(BUDGET_MS, 0.0)
        self.assertLessEqual(BUDGET_MS, 250.0)

    def test_registered_in_run_bot(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"speedc187"', src, "必须在 run_bot.STRATEGY_FACTORIES 注册")


if __name__ == "__main__":
    unittest.main()
