# -*- coding: utf-8 -*-
"""「入席等到秒 ≥ target」机制 + 驱动逐臂选项 的单测（预登记实验 STATUS §9.87 的底座）。

关键不变量：
  ① `wait_seconds_for(sec, target)`：窗口内返回 0、否则返回到目标的秒数；
  ② `match_super` 真的在 `/api/match` 之前调用它；
  ③ `_ab_driver.arm_extra_args` 只给**配置了**的臂追加 `--wait-until-second`；
  ④ `speedtugc_w50` 与 `speedtugc` **打法完全相同**（同一实现，只是名字不同）。
"""
import importlib.util
import inspect
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


ms = _load("ms_wait", "tools/match_super.py")
drv = _load("drv_wait", "var/_ab_driver.py")


class TestWaitUntilSecond(unittest.TestCase):
    def test_wait_seconds_for(self):
        self.assertEqual(ms.wait_seconds_for(10, 50), 40)
        self.assertEqual(ms.wait_seconds_for(49, 50), 1)
        self.assertEqual(ms.wait_seconds_for(50, 50), 0)
        self.assertEqual(ms.wait_seconds_for(59, 50), 0)
        self.assertEqual(ms.wait_seconds_for(None, 50), 0)
        self.assertEqual(ms.wait_seconds_for("x", 50), 0)

    def test_wired_before_match(self):
        src = inspect.getsource(ms.main)
        self.assertIn("wait_until_second(args.wait_until_second)", src)
        self.assertLess(src.index("wait_until_second(args.wait_until_second)"),
                        src.index("api_match()"), "等待必须发生在 /api/match 之前")
        self.assertIn("--wait-until-second", inspect.getsource(ms.main))

    def test_stamp_taken_after_wait(self):
        """★ 2026-09-17 修：`stamp`（= 房目录/日志名，所有"入席秒"分析的口径）必须在**等待之后**取。

        原实现把它放在 wait 之前 ⇒ B 臂目录名记的是"准备入席"的时刻（如 23:33:29），
        而真正入席在 23:33:50 ⇒ `var/_pool_signal_test.py --by-arm` 的**操纵检查**会把 B 臂
        读成"≥50 占比 0%"（实验被误判为"没等到"）。这条不变量防止回归。
        """
        src = inspect.getsource(ms.main)
        self.assertLess(src.index("wait_until_second(args.wait_until_second)"),
                        src.index("stamp = time.strftime"),
                        "stamp 必须取在等待之后（否则入席秒分析口径错）")
        self.assertLess(src.index("stamp = time.strftime"), src.index("api_match()"))


class TestArmExtraArgs(unittest.TestCase):
    CFG = {"arms": ["speedtugc", "speedtugc_w50"],
           "arm_opts": {"speedtugc_w50": {"wait_until_second": 50}}}

    def _nogw(self):
        """一个**不存在**的全局开关路径 ⇒ 让这些用例与真实 var/.wait_until_second 无关（hermetic）。"""
        import tempfile, os
        d = tempfile.mkdtemp(prefix="nogw_")
        self.addCleanup(lambda: None)
        return os.path.join(d, ".wait_until_second")

    def test_configured_arm_gets_flag(self):
        self.assertEqual(drv.arm_extra_args("speedtugc_w50", self.CFG, self._nogw()),
                         ["--wait-until-second", "50"])

    def test_other_arm_gets_nothing(self):
        # ★ 2026-09-17：显式传"不存在"的全局开关路径 ⇒ 只测"没有逐臂设置、也没有全局开关"这一情形
        self.assertEqual(drv.arm_extra_args("speedtugc", self.CFG, self._nogw()), [])
        self.assertEqual(drv.arm_extra_args("speedtugc", {}, self._nogw()), [])
        self.assertEqual(drv.arm_extra_args("x", None, self._nogw()), [])

    def test_global_switch_applies_to_arms_without_opt(self):
        """全局 `var/.wait_until_second` 生效时，**没有逐臂设置**的臂也要等（所有臂一起等 ⇒ 对照仍公平）。"""
        import io as _io, tempfile, os
        fd, g = tempfile.mkstemp(prefix="gw_")
        os.close(fd)
        with _io.open(g, "w", encoding="utf-8") as f:
            f.write("50")
        self.addCleanup(os.unlink, g)
        self.assertEqual(drv.arm_extra_args("speedtugc", {}, g), ["--wait-until-second", "50"])
        self.assertEqual(drv.arm_extra_args("speedc152", {"arms": ["speedtugc", "speedc152"]}, g),
                         ["--wait-until-second", "50"])

    def test_per_arm_opt_beats_global(self):
        """逐臂显式设置优先于全局（池子式实验仍在自己的臂上用 50；其他臂才跟全局）。"""
        import io as _io, tempfile, os
        fd, g = tempfile.mkstemp(prefix="gw2_")
        os.close(fd)
        with _io.open(g, "w", encoding="utf-8") as f:
            f.write("50")
        self.addCleanup(os.unlink, g)
        cfg = {"arm_opts": {"x": {"wait_until_second": 30}}}
        self.assertEqual(drv.arm_extra_args("x", cfg, g), ["--wait-until-second", "30"])

    def test_bad_value_ignored(self):
        cfg = {"arm_opts": {"a": {"wait_until_second": "50"}}}
        import tempfile, os
        missing = os.path.join(tempfile.gettempdir(), "hm_missing_wait_cfg_never_exists")
        self.assertEqual(drv.arm_extra_args("a", cfg, missing), [])

    def test_driver_uses_helper(self):
        src = inspect.getsource(drv.main)
        self.assertIn("arm_extra_args(strat, cfg)", src)


class TestAliasSamePolicy(unittest.TestCase):
    def test_same_class_and_behaviour(self):
        import run_bot
        a = run_bot.STRATEGY_FACTORIES["speedtugc"]()
        b = run_bot.STRATEGY_FACTORIES["speedtugc_w50"]()
        self.assertIs(type(a), type(b), "别名必须是同一实现（只换名字）")
        # speedtugc 的默认显示名是类的默认值（speedTUGC）；别名显式传了 name
        self.assertEqual(b.name, "speedtugc_w50")


ctl = _load("ctl_armopt", "tools/ab_ctl.py")


class TestAbCtlArmOpts(unittest.TestCase):
    """`ab_ctl start ... --arm-opt=策略.键=值` → `.ab_mode.arm_opts` 的往返。"""

    def test_parse_and_build(self):
        arms, rooms, bundles, opts, _started = ctl.parse_start_args(
            ["speedtugc,speedtugc_w50", "1", "--bundles=speedtugc_w50",
             "--arm-opt=speedtugc_w50.wait_until_second=50"])
        self.assertEqual(arms, ["speedtugc", "speedtugc_w50"])
        self.assertEqual(rooms, 1)
        self.assertEqual(bundles, ["speedtugc_w50"])
        self.assertEqual(opts, {"speedtugc_w50": {"wait_until_second": 50}})
        cfg = ctl.build_cfg(arms, rooms, bundles, arm_opts=opts)
        self.assertEqual(cfg["arm_opts"]["speedtugc_w50"]["wait_until_second"], 50)
        self.assertEqual(cfg["bundles"], ["speedtugc_w50"])

    def test_bad_spec_rejected(self):
        with self.assertRaises(SystemExit):
            ctl.parse_start_args(["a,b", "--arm-opt=bogus"])


wp = _load("wait_policy_t", "tools/wait_policy.py")


class TestKeeperWaitArg(unittest.TestCase):
    """`var/.wait_until_second`（全局启用开关）→ 给 match_super 传参。

    ⚠ 这里**只 import 安全模块** `tools/wait_policy.py`；绝不能 import `var/_keeper.py`
    （它在模块级调用 main()，import 即起守夜 —— 既有 test_keeper_yield 就是只读源码来规避）。
    """

    def _tmp(self, text):
        import tempfile
        fd, p = tempfile.mkstemp()
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.unlink, p)
        return p

    def test_valid(self):
        self.assertEqual(wp.wait_args(self._tmp("50")), ["--wait-until-second", "50"])
        self.assertEqual(wp.wait_args(self._tmp(" 0 ")), ["--wait-until-second", "0"])

    def test_invalid_returns_empty(self):
        self.assertEqual(wp.wait_args(self._tmp("abc")), [])
        self.assertEqual(wp.wait_args(self._tmp("99")), [])
        self.assertEqual(wp.wait_args(self._tmp("")), [])
        self.assertEqual(wp.wait_args("/nonexistent/path"), [])
