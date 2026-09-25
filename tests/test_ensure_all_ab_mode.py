# -*- coding: utf-8 -*-
"""`var/_ensure_all.py` 的**A/B 模式**分支单测（此前无覆盖）。

为什么必须（E002 关键路径）：A/B 期间排批由 `_ab_driver.py` 负责，`_ensure_all` 必须在
**驱动不在时把它拉起来**、而**绝不能**去拉 `_keeper.py`（否则同账号两个链 = E002）。
另外要钉住**模式优先级**：两个哨兵同时存在时，`official_mode` 必须优先（正式赛期间不得起 A/B）。

安全：所有哨兵路径都换成 tempfile，**绝不触碰真实的 var/.ab_mode 或 var/.official_mode**。
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)      # main() 有 __main__ 守卫 ⇒ import 安全
    return m


ea = _load("ensure_all_abmode", "var/_ensure_all.py")


class TestEnsureAllAbMode(unittest.TestCase):
    def _tmp_flag(self, name, present=True):
        fd, p = tempfile.mkstemp(prefix="flag_", suffix=name)
        os.close(fd)
        if not present:
            os.unlink(p)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return p

    def _run(self, ab_present, official_present, running=(), spec_present=False):
        ab = self._tmp_flag(".ab_mode", ab_present)
        off = self._tmp_flag(".official_mode", official_present)
        spec = self._tmp_flag(".official_spec.json", spec_present)
        fd_l, logp = tempfile.mkstemp(prefix="log_", suffix=".log")
        os.close(fd_l)
        self.addCleanup(lambda: os.path.exists(logp) and os.unlink(logp))
        self._last_log = logp
        # ★ R1537：KEEPALIVE_OUT 也指向 temp —— 保证“测试绝不写生产 var/”（本文件第 79 行那条教训）
        ka = os.path.join(os.path.dirname(logp), 'ka_keepalive.out')
        old = (ea.AB_FLAG, ea.FLAG, ea.LOG_PATH, ea.SPEC, ea.KEEPALIVE_OUT,
               ea._has, ea._start, ea._fm.handle_pause_on_startup)
        started = []
        ea.AB_FLAG, ea.FLAG, ea.LOG_PATH, ea.SPEC, ea.KEEPALIVE_OUT = ab, off, logp, spec, ka
        ea._fm.handle_pause_on_startup = lambda: False
        running = set(running)
        ea._has = lambda name: name in running
        ea._start = lambda name, *a, **k: started.append(name)
        try:
            ea.main()
        finally:
            (ea.AB_FLAG, ea.FLAG, ea.LOG_PATH, ea.SPEC, ea.KEEPALIVE_OUT,
             ea._has, ea._start, ea._fm.handle_pause_on_startup) = old
        return started

    def test_start_writes_child_output_when_log_path_given(self):
        """★ R1537：`_start(..., log_path=)` 必须把子进程输出**真的**落到该文件。

        本脚本由计划任务用 pythonw（无控制台）起 ⇒ 只靠 DEVNULL 的话“启动即崩”不留证据；
        官方 keepalive 这条路必须能留证。这里用假脚本 + 临时 ROOT 做**功能**验证
        （不是只查源码字符串），并**抓住 Popen 对象显式 wait**，避免漏进程/GC 警告。
        """
        import time as _t
        d = tempfile.mkdtemp(prefix="start_probe_")
        vd = os.path.join(d, "var")
        os.makedirs(vd)
        with io.open(os.path.join(vd, "probe.py"), "w", encoding="utf-8") as f:
            f.write(u"print('PROBE-' + 'OK')\n")
        out = os.path.join(d, "out.txt")
        created = []
        real_popen = ea.subprocess.Popen

        def _spy(*a, **k):
            pr = real_popen(*a, **k)
            created.append(pr)
            return pr

        old_root = ea.ROOT
        ea.ROOT = d
        try:
            with mock.patch.object(ea.subprocess, "Popen", _spy):
                ea._start("probe.py", log_path=out)
            self.assertEqual(1, len(created), "应当真的起了一个子进程")
            created[0].wait(timeout=30)
            with io.open(out, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("PROBE-OK", body, u"子进程输出必须落进 log_path 指定的文件")
        finally:
            ea.ROOT = old_root

    def test_ab_mode_starts_driver_not_keeper(self):
        started = self._run(ab_present=True, official_present=False)
        self.assertIn("_ab_driver.py", started, "A/B 期间必须保证驱动活着")
        self.assertNotIn("_keeper.py", started, "A/B 期间绝不可起 keeper（E002）")

    def test_ab_mode_does_not_double_start(self):
        started = self._run(ab_present=True, official_present=False,
                            running=("_watchdog.py", "_ab_driver.py"))
        self.assertEqual(started, [], "驱动已在跑则不得重复启动")

    def test_official_takes_precedence_over_ab(self):
        started = self._run(ab_present=True, official_present=True)
        self.assertIn("_official_keepalive.py", started)
        self.assertNotIn("_ab_driver.py", started, "正式赛优先：不得起 A/B 驱动")
        self.assertNotIn("_keeper.py", started)

    def test_official_warning_goes_to_temp_log_not_production(self):
        """**非 hermetic 测试事故的回归**：正式赛分支缺 .official_spec.json 时会写一条警告；
        该警告**必须落在测试自己的 tempfile**，绝不追加到生产的 var/_ensure_all.log。

        背景（2026-09-17）：本测试原先只替换了 flag 路径、**没替换日志路径** ⇒ 每次跑全量回归都会
        往真实 _ensure_all.log 追加两条"官方赛重启缺 .official_spec.json"，
        让后来看日志的人误以为线上进过 official_mode（实测 .official_mode 全程不存在）。
        """
        prod = os.path.join(ROOT, "var", "_ensure_all.log")
        before = (os.path.getsize(prod), os.path.getmtime(prod)) if os.path.exists(prod) else None
        self._run(ab_present=False, official_present=True, spec_present=False)
        with io.open(self._last_log, encoding="utf-8") as fh:
            self.assertIn("官方赛重启缺 .official_spec.json", fh.read(),
                          "警告应写进测试的 tempfile")
        after = (os.path.getsize(prod), os.path.getmtime(prod)) if os.path.exists(prod) else None
        self.assertEqual(before, after, "生产日志被测试污染了")

    def test_real_flags_untouched(self):
        real_off = os.path.join(ROOT, "var", ".official_mode")
        before = os.path.exists(real_off)
        self._run(ab_present=False, official_present=True, spec_present=True)
        after = os.path.exists(real_off)
        self.assertEqual(before, after, "测试不得创建/删除真实 official_mode 哨兵")

        real_ab = os.path.join(ROOT, "var", ".ab_mode")
        before_ab = os.path.exists(real_ab)
        self._run(ab_present=True, official_present=False, spec_present=True)
        after_ab = os.path.exists(real_ab)
        self.assertEqual(before_ab, after_ab, "测试不得创建/删除真实 ab_mode 哨兵")


if __name__ == "__main__":
    unittest.main()
