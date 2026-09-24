# -*- coding: utf-8 -*-
"""并发交替 A/B 相关单测。

安全：所有哨兵路径都换成 tempfile，**绝不触碰真实的 var/.ab_mode**（那会停掉 keeper）。
"""
import importlib.util
import io
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wd = _load("wd2", "var/_watchdog.py")
ea = _load("ea2", "var/_ensure_all.py")
ro = _load("ro2", "tools/ab_readout.py")


class TestAbMode(unittest.TestCase):
    def setUp(self):
        # 记录**真实**哨兵状态：测试只负责不改变它（线上可能正在跑 A/B 或官方赛）
        self._real_before = {n: os.path.exists(os.path.join(ROOT, "var", n))
                             for n in (".ab_mode", ".official_mode")}
        self.tmp = tempfile.mkdtemp(prefix="abmode_")
        self.ab = os.path.join(self.tmp, ".ab_mode")
        self.off = os.path.join(self.tmp, ".official_mode")
        self.saved = (wd.AB_FLAG, wd.OFFICIAL_FLAG, ea.AB_FLAG, ea.FLAG)
        wd.AB_FLAG = ea.AB_FLAG = self.ab
        wd.OFFICIAL_FLAG = ea.FLAG = self.off

    def tearDown(self):
        (wd.AB_FLAG, wd.OFFICIAL_FLAG, ea.AB_FLAG, ea.FLAG) = self.saved

    def test_off_by_default(self):
        self.assertFalse(wd.ab_mode())
        self.assertFalse(ea.ab_mode())

    def test_on_when_sentinel_present(self):
        with io.open(self.ab, "w", encoding="utf-8") as f:
            f.write("{}")
        self.assertTrue(wd.ab_mode(), "watchdog 必须能识别 A/B 模式")
        self.assertTrue(ea.ab_mode(), "计划任务必须能识别 A/B 模式（否则会双开 keeper→E002）")

    def test_real_sentinels_untouched(self):
        """不变量：测试**不得改变**真实哨兵的状态（线上可能正在跑 A/B / 官方赛）。"""
        for n, before in self._real_before.items():
            now = os.path.exists(os.path.join(ROOT, "var", n))
            self.assertEqual(before, now, "测试改变了真实哨兵 %s 的状态" % n)


class TestAbReadout(unittest.TestCase):
    def _mk(self, strategy, net_target):
        d = tempfile.mkdtemp(prefix="abr_")
        p = os.path.join(d, "r.jsonl")
        with io.open(p, "w", encoding="utf-8") as f:
            for _ in range(5):
                f.write(json.dumps({"strategy": strategy, "ts": "2026-09-15 20:00:00",
                                    "ranking": [{"user_id": ro.ME, "total_score": net_target,
                                                 "rank": 1},
                                                {"user_id": "a", "total_score": 0},
                                                {"user_id": "b", "total_score": 0},
                                                {"user_id": "c", "total_score": 0}]}) + "\n")
        return p

    def test_rooms_for_filters_by_strategy_and_computes_net(self):
        p = self._mk("speedtugc", 60)
        old = ro.RANKING
        ro.RANKING = p
        try:
            rs = ro.rooms_for("speedtugc")
            self.assertEqual(len(rs), 5)
            self.assertAlmostEqual(rs[0]["net"], 60.0)
            self.assertEqual(ro.rooms_for("nonexistent"), [])
            # since 过滤
            self.assertEqual(ro.rooms_for("speedtugc", since="2026-09-16 00:00:00"), [])
        finally:
            ro.RANKING = old


class TestAbCtl(unittest.TestCase):
    def test_start_rejects_unregistered_strategy(self):
        ctl = _load("ctl", "tools/ab_ctl.py")
        old_ab = ctl.AB
        ctl.AB = os.path.join(tempfile.mkdtemp(prefix="abctl_"), ".ab_mode")
        try:
            with self.assertRaises(SystemExit):
                ctl.start(["speedtugc", "definitely_not_a_strategy"], 1)
            self.assertFalse(os.path.exists(ctl.AB), "校验失败时不得写出哨兵")
        finally:
            ctl.AB = old_ab


class TestAbDriverOnceDry(unittest.TestCase):
    """驱动的一次性干跑：验证交替 + 状态 + 不启动任何进程。"""

    def test_once_dry_alternates_and_writes_state(self):
        drv = _load("drv", "var/_ab_driver.py")
        tmp = tempfile.mkdtemp(prefix="abd_")
        old = (drv.AB, drv.STATE)
        drv.AB = os.path.join(tmp, ".ab_mode")
        drv.STATE = os.path.join(tmp, "_ab_state_v2.json")
        try:
            with io.open(drv.AB, "w", encoding="utf-8") as f:
                f.write(json.dumps({"a": "speedtugc", "b": "speedc130", "rooms": 1}))
            buf = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buf):      # 捕获，不污染测试输出
                rc1 = drv.once_dry(); rc2 = drv.once_dry()
            out = buf.getvalue()
            self.assertEqual((rc1, rc2), (0, 0))
            self.assertIn("arm=speedtugc strategy=speedtugc", out)
            self.assertIn("arm=speedc130 strategy=speedc130", out, "第二次必须换到另一臂")
            st = json.loads(io.open(drv.STATE, encoding="utf-8").read())
            self.assertEqual(st["counts"], {"speedtugc": 1, "speedc130": 1})
            self.assertEqual(st["next_idx"], 0)
        finally:
            drv.AB, drv.STATE = old

class TestAbDriverGuard(unittest.TestCase):
    """熔断器语义已迁移到 tests/test_ab_guard.py（2026-09-16 12:10 修正为「候选 − 基线」口径）。

    这里只留一条跨文件哨兵：保证 _ab_driver 仍暴露 guard_candidate，且签名是新的四元组，
    防止有人把它改回"只看候选绝对净值"的旧实现而两处测试文件不再互相覆盖。
    """

    def test_guard_api_is_the_paired_one(self):
        drv = _load("drv_guard_sentinel", "var/_ab_driver.py")
        orig = drv.arm_recent_net
        try:
            drv.arm_recent_net = lambda strategy, since: ([-350.0] * 6 if strategy == "cand" else [0.0] * 6)
            out = drv.guard_candidate("cand", "base", None)
        finally:
            drv.arm_recent_net = orig
        self.assertEqual(len(out), 4, "guard_candidate 必须返回 (abort, mean, n, base_mean)")
        abort, mean, n, base = out
        self.assertTrue(abort, "候选比基线差 -350/房（满 6 房）应触发快档")
        self.assertEqual(n, drv.GUARD_MIN_ROOMS)
        self.assertAlmostEqual(base, 0.0)

class TestAbDriverNArms(unittest.TestCase):
    """N 臂支持（cfg["arms"]）+ 旧 {a,b} 向后兼容。"""

    def _cfg(self, obj):
        d = tempfile.mkdtemp(prefix="abn_")
        ab = os.path.join(d, ".ab_mode")
        with io.open(ab, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj))
        return ab

    def test_arms_of_supports_both_shapes(self):
        drv = _load("drv7", "var/_ab_driver.py")
        self.assertEqual(drv.arms_of({"arms": ["x", "y", "z"]}), ["x", "y", "z"])
        self.assertEqual(drv.arms_of({"a": "x", "b": "y"}), ["x", "y"])

    def test_once_dry_round_robins_three_arms(self):
        drv = _load("drv8", "var/_ab_driver.py")
        ab = self._cfg({"arms": ["speedtugc", "speedc130", "speedc073w4"], "rooms": 1})
        tmpd = os.path.dirname(ab)
        old = (drv.AB, drv.STATE)
        drv.AB, drv.STATE = ab, os.path.join(tmpd, "s.json")
        import contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                for _ in range(4):
                    drv.once_dry()
        finally:
            drv.AB, drv.STATE = old
        out = buf.getvalue()
        for name in ("speedtugc", "speedc130", "speedc073w4"):
            self.assertIn("strategy=%s" % name, out)
        st = json.loads(io.open(drv.STATE if False else os.path.join(tmpd, "s.json"),
                                encoding="utf-8").read())
        self.assertEqual(st["counts"].get("speedtugc"), 2, "4 次轮转 → 第 1 臂 2 次")
        self.assertEqual(st["counts"].get("speedc130"), 1)
        self.assertEqual(st["counts"].get("speedc073w4"), 1)
        self.assertEqual(st["next_idx"], 1, "4 次后应指向第 2 臂")

if __name__ == "__main__":
    unittest.main()
