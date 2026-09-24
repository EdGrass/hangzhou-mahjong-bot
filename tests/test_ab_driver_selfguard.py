# -*- coding: utf-8 -*-
"""`var/_ab_driver.py::other_driver_pids` 单测 —— **驱动自守卫**（防"两驱动同排批 = E002"）。

为什么（本会话第四次加固 E002 路径）：`_watchdog` 在 A/B 模式也"缺驱动就拉起"，它与 `ab_ctl.py start`
之间有极窄竞态（写哨兵→spawn 几十毫秒；watchdog 每 90s 查一次）⇒ 两个驱动同看一份 `.ab_mode` ⇒ 两房并发。
自守卫让**重复实例立刻退出、且绝不写基线策略文件**。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


drv = _load("ab_driver_selfguard_t", "var/_ab_driver.py")


class TestDriverSelfGuard(unittest.TestCase):
    def test_detects_other_driver(self):
        rows = [(11, ["python", "var/_ab_driver.py"]),
                (22, ["python", "-X", "utf8", "var/_ab_driver.py"]),
                (33, ["python", "tools/preflight.py"])]
        self.assertEqual(drv.other_driver_pids(rows, 11), [22], "应只报出别的驱动（不含自己）")

    def test_self_only_is_empty(self):
        self.assertEqual(drv.other_driver_pids([(11, ["python", "var/_ab_driver.py"])], 11), [])

    def test_unrelated_processes_ignored(self):
        rows = [(1, ["python", "var/_ensure_all.py"]),
                (2, ["python", "tools/match_super.py", "--rooms", "1"]),
                (3, ["python", "run_bot.py", "tok", "a_1"]),
                (4, ["python", "var/_watchdog.py"])]
        self.assertEqual(drv.other_driver_pids(rows, 99), [])

    def test_empty_inputs(self):
        self.assertEqual(drv.other_driver_pids([], 1), [])
        self.assertEqual(drv.other_driver_pids(None, 1), [])
        self.assertEqual(drv.other_driver_pids([(1, [])], 2), [])


if __name__ == "__main__":
    unittest.main()
