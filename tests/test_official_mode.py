# -*- coding: utf-8 -*-
"""官方赛哨兵单测：验证「停止测试房自愈」的两条路径都被哨兵拦住。

回归背景：9/17 正式赛操作单要求先停测试房 keeper，但 watchdog 每 90s、
计划任务每 5min 都会把 keeper 拉回来 → 与正式赛同账号并发（E002）。
测试用 tempfile 替换哨兵路径，**绝不触碰真实 var/.official_mode**。
"""
import importlib.util
import io
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wd = _load("wd", os.path.join(ROOT, "var", "_watchdog.py"))
ea = _load("ea", os.path.join(ROOT, "var", "_ensure_all.py"))


class TestOfficialSentinel(unittest.TestCase):
    def setUp(self):
        self._real_off = os.path.exists(os.path.join(ROOT, "var", ".official_mode"))
        self.tmp = tempfile.mkdtemp(prefix="offmode_")
        self.flag = os.path.join(self.tmp, ".official_mode")
        self._wd_flag, wd.OFFICIAL_FLAG = wd.OFFICIAL_FLAG, self.flag
        self._ea_flag, ea.FLAG = ea.FLAG, self.flag

    def tearDown(self):
        wd.OFFICIAL_FLAG = self._wd_flag
        ea.FLAG = self._ea_flag

    def test_off_by_default(self):
        self.assertFalse(wd.official_mode())
        self.assertFalse(ea.official_mode())

    def test_on_when_sentinel_present(self):
        with open(self.flag, "w", encoding="utf-8") as f:
            f.write("x")
        self.assertTrue(wd.official_mode())
        self.assertTrue(ea.official_mode())

    def test_off_again_after_removal(self):
        with open(self.flag, "w", encoding="utf-8") as f:
            f.write("x")
        os.remove(self.flag)
        self.assertFalse(wd.official_mode())
        self.assertFalse(ea.official_mode())

    def test_real_flag_untouched_by_tests(self):
        """不变量：测试不得改变真实 .official_mode 的状态（线上可能正在打正式赛）。"""
        real = os.path.join(ROOT, "var", ".official_mode")
        self.assertEqual(getattr(self, "_real_off", False), os.path.exists(real),
                         "测试改变了真实 .official_mode 的状态")


class TestEnsureAllStartsOfficialKeepalive(unittest.TestCase):
    """回归：正式赛期间 _ensure_all 必须保证 _official_keepalive.py 活着，
    否则 keepalive 自己死掉就无人拉起（与 keeper 无人管同类缺口）。"""

    def test_starts_official_keepalive_when_missing(self):
        tmp = tempfile.mkdtemp(prefix="eaoff_")
        flag = os.path.join(tmp, ".official_mode")
        with io.open(flag, "w", encoding="utf-8") as f:
            f.write("x")
        old = (ea.FLAG, ea._has, ea._start, ea._fm.handle_pause_on_startup)
        started, running = [], set()
        ea.FLAG = flag
        ea._has = lambda name: name in running
        ea._start = lambda name, *a: started.append(name)
        ea._fm.handle_pause_on_startup = lambda: False
        try:
            ea.main()
        finally:
            ea.FLAG, ea._has, ea._start, ea._fm.handle_pause_on_startup = old
        self.assertIn("_official_keepalive.py", started, "必须拉起正式赛 keepalive")
        self.assertNotIn("_keeper.py", started, "正式赛期间绝不可拉测试房 keeper")

    def test_does_not_double_start_when_already_running(self):
        tmp = tempfile.mkdtemp(prefix="eaoff2_")
        flag = os.path.join(tmp, ".official_mode")
        with io.open(flag, "w", encoding="utf-8") as f:
            f.write("x")
        old = (ea.FLAG, ea._has, ea._start, ea._fm.handle_pause_on_startup)
        started = []
        ea.FLAG = flag
        ea._has = lambda name: name in ("_watchdog.py", "_official_keepalive.py")
        ea._start = lambda name, *a: started.append(name)
        ea._fm.handle_pause_on_startup = lambda: False
        try:
            ea.main()
        finally:
            ea.FLAG, ea._has, ea._start, ea._fm.handle_pause_on_startup = old
        self.assertEqual(started, [], "已在运行则不得重复启动")


class TestOfficialKeepaliveExclusive(unittest.TestCase):
    """E002 红线加固（2026-09-17）：`_official_keepalive._existing()` 必须把**整条测试房链路**
    都算成占用，而不只是 run_bot。

    为什么值得钉：测试房链路是 `_keeper` → `match_super` → `run_bot`，而 **match_super 在"等房期"
    合法地没有 run_bot 子进程**（现在还有 `--wait-until-second` 先睡最多 59 秒）。
    旧守卫只认 run_bot/keep_alive/_official_keepalive ⇒ 那种时刻手工拉起正式赛 keepalive 就会放行，
    等 match_super 入房即 **同账号两个 run_bot = E002**。
    """

    def _mod(self):
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "okp2", os.path.join(root, "var", "_official_keepalive.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def _existing_with(self, argv):
        m = self._mod()

        class _P:
            info = {"pid": 424242, "cmdline": argv, "exe": "python.exe"}

        old = m.psutil.process_iter
        m.psutil.process_iter = lambda *a, **k: [_P()]
        try:
            return m._existing()
        finally:
            m.psutil.process_iter = old

    def test_flags_match_super_without_run_bot(self):
        self.assertEqual(self._existing_with(
            ["python.exe", "-X", "utf8", "-u", "D:/hangzhouMaj/tools/match_super.py",
             "--rooms", "1", "--strategy", "speedtugc", "--wait-until-second", "50"]),
            [424242], "等房期的 match_super 必须算占用（否则 E002）")

    def test_flags_keeper(self):
        self.assertEqual(self._existing_with(
            ["python.exe", "D:/hangzhouMaj/var/_keeper.py", "speedtugc", "4"]), [424242])

    def test_flags_run_bot_and_official(self):
        for argv in (["python.exe", "run_bot.py", "tok"],
                     ["python.exe", "-X", "utf8", "var/_official_keepalive.py"]):
            self.assertEqual(self._existing_with(argv), [424242], argv)

    def test_ignores_unrelated(self):
        self.assertEqual(self._existing_with(["python.exe", "tools/ab_readout.py"]), [])


if __name__ == "__main__":
    unittest.main()

class TestOfficialKeepaliveBackoff(unittest.TestCase):
    """正式赛 keepalive 的重启退避：指数增长、封顶 120s，**不设停摆上限**。

    为什么值得钉：正式赛是一次性事件，`run_bot` 非零退出（网络抖动/平台 5xx）时必须一直重试；
    但固定 5s 重试会在持续失败时形成高频重启。策略是"退避但永不放弃"（由人工 _exit_official 收尾）。
    """

    def _delay(self):
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "okp", os.path.join(root, "var", "_official_keepalive.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.next_delay

    def test_exponential_and_capped(self):
        f = self._delay()
        self.assertEqual(f(0), 5)
        self.assertEqual(f(1), 5)
        self.assertEqual(f(2), 10)
        self.assertEqual(f(3), 20)
        self.assertEqual(f(4), 40)
        self.assertEqual(f(5), 80)
        self.assertEqual(f(6), 120)
        self.assertEqual(f(20), 120)          # 封顶
        self.assertGreater(f(20), 0)          # 永不退化为 0（不会忙等）
