# -*- coding: utf-8 -*-
"""`tools/ab_ctl.py` 的**参数解析与配置构造**单测（纯函数）。### 这一层为什么必须有测试

预登记判据（组合臂 1.50/150 房 vs 单变量 1.96/100 房）的载体是 `.ab_mode` 里的 `bundles` 字段。
只要 `start()` 没把这个字段写进去，读表/采用工具就会**把组合臂当单变量**用更严的阈值 ⇒ **整个战役白跑**。
2026-09-16 实测：`start()` 原来**只在 ≥3 臂分支写 bundles**，而我们的主力形态正是"**2 臂 + 一个组合臂候选**"。
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("abctl", os.path.join(ROOT, "tools", "ab_ctl.py"))
abctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abctl)


class TestParseStartArgs(unittest.TestCase):
    def test_arms_rooms_bundles(self):
        self.assertEqual(abctl.parse_start_args(["speedtugc,speedc146", "1", "--bundles=speedc146"]),
                         (["speedtugc", "speedc146"], 1, ["speedc146"], {}, None))

    def test_order_independent(self):
        self.assertEqual(abctl.parse_start_args(["a,b", "--bundles=b", "2"]),
                         (["a", "b"], 2, ["b"], {}, None))

    def test_defaults(self):
        self.assertEqual(abctl.parse_start_args(["a,b"]), (["a", "b"], 1, [], {}, None))

    def test_multiple_bundles_and_spaces(self):
        self.assertEqual(abctl.parse_start_args(["a, b, c", "--bundles=b,c"]),
                         (["a", "b", "c"], 1, ["b", "c"], {}, None))

    def test_started_passthrough(self):
        """★回归：`--started=` 必须能带进来 —— 测试赛会打断战役（19:00 切/22:00 恢复），
        而 `ab_readout` 的判定**按 started 过滤**；恢复时不传回原 started 就会把已积累的房判为
        "不属于本役" ⇒ 12 房机制闸门与 150 房采用计数**全部清零**。"""
        a, r, bd, ao, st = abctl.parse_start_args(
            ["speedtugc,speedc151,speedc163,speedc186", "1",
             "--bundles=speedc163,speedc186", "--started=2026-09-17 11:22:11"])
        self.assertEqual(st, "2026-09-17 11:22:11")
        cfg = abctl.build_cfg(a, r, bd, started=st, arm_opts=ao)
        self.assertEqual(cfg["started"], "2026-09-17 11:22:11")
        # 不带该参数时仍走"现在"（默认行为不变）
        self.assertIsNone(abctl.parse_start_args(["a,b"])[4])

    def test_missing_args_raises(self):
        with self.assertRaises(SystemExit):
            abctl.parse_start_args([])


class TestBuildCfg(unittest.TestCase):
    def test_two_arms_keeps_bundles(self):
        """★回归：2 臂 + 组合臂候选时 bundles 必须写进配置（否则判据退化成单变量）。"""
        cfg = abctl.build_cfg(["speedtugc", "speedc146"], 1, ["speedc146"], started="T")
        self.assertEqual(cfg["a"], "speedtugc")
        self.assertEqual(cfg["b"], "speedc146")
        self.assertEqual(cfg["bundles"], ["speedc146"])
        self.assertEqual(cfg["rooms"], 1)

    def test_three_arms_uses_arms_key(self):
        cfg = abctl.build_cfg(["a", "b", "c"], 1, ["b"], started="T")
        self.assertEqual(cfg["arms"], ["a", "b", "c"])
        self.assertEqual(cfg["bundles"], ["b"])
        self.assertNotIn("a", cfg)

    def test_no_bundle_key_when_empty(self):
        cfg = abctl.build_cfg(["a", "b"], "1", [], started="T")
        self.assertNotIn("bundles", cfg)
        self.assertEqual(cfg["rooms"], 1)

    def test_rooms_coerced_to_int(self):
        self.assertEqual(abctl.build_cfg(["a", "b"], "3", None, started="T")["rooms"], 3)


if __name__ == "__main__":
    unittest.main()
