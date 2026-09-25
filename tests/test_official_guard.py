# -*- coding: utf-8 -*-
"""`var/_official_guard.py` 契约测试（R1164）。

为什么必须钉住：它会在「官方模式 + keepalive 缺失」时**真的拉起一个进程**。
所以三条路径必须精确：
  ① 非官方模式 ⇒ 严格 no-op（不查进程、不起进程、不写日志）；
  ② 官方模式但 keepalive 在 ⇒ 不动作；
  ③ 官方模式且 keepalive 缺失 ⇒ 按 `official_argv()`（spec）拉起，**不自己拼参数**；
  ④ spec 无效 ⇒ 不动作（宁可交 5 分钟兜底，也不用错令牌/策略）。
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load():
    spec = importlib.util.spec_from_file_location(
        "official_guard_t", os.path.join(ROOT, "var", "_official_guard.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["official_guard_t"] = m
    spec.loader.exec_module(m)
    return m


g = _load()


class TestOfficialGuard(unittest.TestCase):
    def _flag(self, exists):
        fd, p = tempfile.mkstemp(suffix=".sentinel")
        os.close(fd)
        if not exists:
            os.unlink(p)
        else:
            self.addCleanup(os.unlink, p)
        return p

    def test_noop_when_not_official_mode(self):
        """① 非官方模式：严格 no-op（不查进程、不起进程）。"""
        with mock.patch.object(g, "FLAG", self._flag(False)), \
             mock.patch.object(g, "_has") as has, \
             mock.patch.object(g, "_log") as lg, \
             mock.patch.object(g.subprocess, "Popen") as popen:
            self.assertEqual(g.main(), 0)
            has.assert_not_called(); popen.assert_not_called(); lg.assert_not_called()

    def test_noop_when_keepalive_alive(self):
        """② 官方模式 + keepalive 在：不动作。"""
        with mock.patch.object(g, "FLAG", self._flag(True)), \
             mock.patch.object(g, "_has", return_value=4242), \
             mock.patch.object(g.subprocess, "Popen") as popen:
            self.assertEqual(g.main(), 0)
            popen.assert_not_called()

    def test_starts_with_spec_argv(self):
        """③ 官方模式 + 缺失：按 spec argv 拉起（不自己拼）。"""
        fake = ["--strategy", "speedc151", "--token-file", "var\\.tok"]
        with mock.patch.object(g, "FLAG", self._flag(True)), \
             mock.patch.object(g, "_has", return_value=None), \
             mock.patch.object(g, "_log"), \
             mock.patch.object(g, "spec_freshness", return_value=(True, "test")), \
             mock.patch.object(g, "_load_ensure_all") as le, \
             mock.patch.object(g.subprocess, "Popen") as popen:
            le.return_value.official_argv.return_value = fake
            self.assertEqual(g.main(), 0)
            self.assertTrue(popen.called)
            argv = popen.call_args[0][0]
            self.assertTrue(argv[-len(fake):] == fake, "必须把 spec argv 原样附在末尾：%r" % (argv,))
            self.assertTrue(any(str(x).endswith("_official_keepalive.py") for x in argv), argv)

    def test_spawn_redirects_child_output(self):
        """★ R1537：本脚本由计划任务用 **pythonw**（无控制台）起 ⇒ 拉起 keepalive 时**必须**重定向输出。

        否则子进程“启动即崩”时日志里只剩一句「✓ 已按 spec 拉起」，**下一条证据都没有**
        （本项目反复抓的“看着成功其实没跑”）。
        """
        import tempfile
        d = tempfile.TemporaryDirectory()
        try:
            out = os.path.join(d.name, "_official_keepalive.out")
            fake = ["--strategy", "speedvalue"]
            with mock.patch.object(g, "FLAG", self._flag(True)), \
                 mock.patch.object(g, "KEEPALIVE_OUT", out), \
                 mock.patch.object(g, "_has", return_value=None), \
                 mock.patch.object(g, "_log"), \
                 mock.patch.object(g, "spec_freshness", return_value=(True, "test")), \
                 mock.patch.object(g, "_load_ensure_all") as le, \
                 mock.patch.object(g.subprocess, "Popen") as popen:
                le.return_value.official_argv.return_value = fake
                self.assertEqual(g.main(), 0)
            kw = popen.call_args[1]
            self.assertIn("stdout", kw, "必须把子进程 stdout 重定向到 %s" % out)
            self.assertEqual(g.subprocess.STDOUT, kw.get("stderr"), "stderr 必须并入同一份日志")
            self.assertTrue(os.path.exists(out), "日志文件应被创建/追加")
        finally:
            d.cleanup()

    def test_no_action_when_spec_missing(self):
        """④ spec 无效：不动作（宁可交兜底）。"""
        with mock.patch.object(g, "FLAG", self._flag(True)), \
             mock.patch.object(g, "_has", return_value=None), \
             mock.patch.object(g, "_log"), \
             mock.patch.object(g, "_load_ensure_all") as le, \
             mock.patch.object(g.subprocess, "Popen") as popen:
            le.return_value.official_argv.return_value = []
            self.assertEqual(g.main(), 1)
            popen.assert_not_called()


class SpecFreshnessTest(unittest.TestCase):
    """★ R1214：spec 新鲜度闸门 —— 防"旧令牌/旧策略"被守卫拉起上场。"""

    def _load_with_spec(self, ts):
        import importlib.util, json, tempfile, os, sys
        m = _load()
        tmp = tempfile.mkdtemp(prefix="ogspec_")
        spec = os.path.join(tmp, ".official_spec.json")
        with io.open(spec, "w", encoding="utf-8") as f:
            json.dump({"strategy": "x", "token_file": "y", "ts": ts}, f)
        m.SPEC = spec
        return m

    def test_fresh_spec_ok(self):
        import datetime as dt
        ts = (dt.datetime.now() - dt.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        m = self._load_with_spec(ts)
        ok, why = m.spec_freshness()
        self.assertTrue(ok, why)

    def test_stale_spec_rejected(self):
        import datetime as dt
        ts = (dt.datetime.now() - dt.timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
        m = self._load_with_spec(ts)
        ok, why = m.spec_freshness()
        self.assertFalse(ok)
        self.assertIn("过期", why)

    def test_missing_spec_rejected(self):
        import os, tempfile
        m = _load()
        m.SPEC = os.path.join(tempfile.mkdtemp(), "nope.json")
        ok, why = m.spec_freshness()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
