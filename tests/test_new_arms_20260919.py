# -*- coding: utf-8 -*-
"""c209~c216 的注册与基本契约（2026-09-19 新增策略的回归保护）。

只做**零成本**检查（不跑决策、不加载大模型之外的额外东西）：
  ① 全部在 `run_bot.STRATEGY_FACTORIES` 里，且能构造；
  ② 继承关系正确（每个候选的"父类含义"）；
  ③ c211 相对 c152 只覆盖 `_want_claim`（单变量）；
  ④ c216 的 `_lagging` 纯逻辑（落后判定）正确。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import run_bot  # noqa: E402


NEW_ARMS = ["speedc209", "speedc210", "speedc211", "speedc212",
            "speedc213", "speedc214", "speedc215", "speedc216"]


class TestNewArmsRegistered(unittest.TestCase):
    def test_all_registered(self):
        for a in NEW_ARMS:
            self.assertIn(a, run_bot.STRATEGY_FACTORIES, a)

    def test_all_constructible(self):
        for a in NEW_ARMS:
            try:
                p = run_bot.STRATEGY_FACTORIES[a]()
            except Exception as e:      # pragma: no cover
                self.fail("%s 构造失败: %r" % (a, e))
            self.assertEqual(p.name, a)


class TestInheritance(unittest.TestCase):
    def _mro(self, name):
        p = run_bot.STRATEGY_FACTORIES[name]()
        return [c.__name__ for c in type(p).__mro__]

    def test_c211_is_c152_subclass(self):
        m = self._mro("speedc211")
        self.assertIn("SpeedC152", m)
        self.assertIn("SpeedC211", m)

    def test_c210_is_c152_subclass(self):
        self.assertIn("SpeedC152", self._mro("speedc210"))

    def test_c216_is_c211_subclass(self):
        m = self._mro("speedc216")
        self.assertIn("SpeedC211", m)
        self.assertIn("SpeedC216", m)


class TestC211SingleVariable(unittest.TestCase):
    """c211 = c152 − C136：只应覆盖 `_want_claim`（外加 __init__）。"""

    def test_only_two_methods(self):
        import io, ast
        with io.open(os.path.join(ROOT, "bot", "speedc211.py"), encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SpeedC211":
                names = [f.name for f in node.body if isinstance(f, ast.FunctionDef)]
        self.assertEqual(sorted(names), ["__init__", "_want_claim"])


class TestC216LagLogic(unittest.TestCase):
    def test_lagging_threshold(self):
        p = run_bot.STRATEGY_FACTORIES["speedc216"]()
        p._seat = 0
        p._scores = [0, 99, 0, 0]          # 落后 99 < LAG(100) ⇒ 不触发
        self.assertFalse(p._lagging())
        p._scores = [0, 100, 0, 0]         # 落后 100 ≥ LAG ⇒ 触发
        self.assertTrue(p._lagging())
        p._scores = [500, 100, 0, 0]       # 我领先 ⇒ 不触发
        self.assertFalse(p._lagging())

    def test_missing_scores_safe(self):
        p = run_bot.STRATEGY_FACTORIES["speedc216"]()
        p._seat = 0
        p._scores = None
        self.assertFalse(p._lagging())
        p._scores = [1, 2]                 # 长度不对
        self.assertFalse(p._lagging())


if __name__ == "__main__":
    unittest.main()
