# -*- coding: utf-8 -*-
"""`var/_exit_official.py::busy_names` 单测 —— 退出官方赛模式前的**E002 守卫**。

背景（本会话加固）：原实现只查 `run_bot.py` / `_official_keepalive.py` ⇒ 若在"批次间隙"
（run_bot 恰好不在、但 `_ab_driver`/`match_super`/`_keeper` 还活着）执行 `_exit_official.py`，
删哨兵后 `_ensure_all` 会拉起 keeper ⇒ 与 A/B 链**同账号并发 = E002**。
本测试钉住"任何 bot 链进程在跑都必须被识别为忙碌"。
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
    spec.loader.exec_module(m)     # main() 有 __main__ 守卫 ⇒ import 安全
    return m


ex = _load("exit_official_t", "var/_exit_official.py")


class TestBusyNames(unittest.TestCase):
    def test_detects_all_bot_chain_processes(self):
        for name in ("run_bot.py", "_official_keepalive.py", "match_super.py",
                     "_ab_driver.py", "_keeper.py"):
            self.assertIn(name, ex.BUSY_NAMES, "%s 必须在拒绝名单里" % name)

    def test_scan_returns_script_names(self):
        cmds = [["python", "-X", "utf8", "var/_ab_driver.py"],
                ["python", "-u", "tools/match_super.py", "--rooms", "1"],
                ["python", "run_bot.py", "tok", "a_1"]]
        self.assertEqual(sorted(ex.busy_names(cmds)), ["_ab_driver.py", "match_super.py", "run_bot.py"])

    def test_ignores_unrelated_scripts(self):
        cmds = [["python", "var/_ensure_all.py"],
                ["python", "tools/preflight.py"],
                ["python", "-X", "utf8", "var/_official_status.py"]]
        self.assertEqual(ex.busy_names(cmds), [])

    def test_empty_inputs(self):
        self.assertEqual(ex.busy_names([]), [])
        self.assertEqual(ex.busy_names(None), [])
        self.assertEqual(ex.busy_names([[]]), [])


if __name__ == "__main__":
    unittest.main()
