# -*- coding: utf-8 -*-
"""`tools/ab_ctl.py:_kill_idle_match_super` 单测：**只在房与房之间**动手，绝不中断在途对局。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("abctl", os.path.join(ROOT, "tools", "ab_ctl.py"))
abctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abctl)


class TestAbStartFastTakeover(unittest.TestCase):
    def setUp(self):
        self._orig = abctl._procs
        self.killed = []
        self._killer = None

    def tearDown(self):
        abctl._procs = self._orig

    def _patch(self, ms, rb):
        abctl._procs = lambda name: list(ms if name == "match_super.py" else
                                        (rb if name == "run_bot.py" else []))

    def test_does_nothing_while_a_room_is_running(self):
        """run_bot 存活 ⇒ 绝不碰 match_super（在途对局是红线）。"""
        self._patch([111], [222])
        import psutil
        calls = []
        orig = psutil.Process
        psutil.Process = lambda pid: calls.append(pid) or type("P", (), {"kill": lambda s: None})()
        try:
            abctl._kill_idle_match_super()
        finally:
            psutil.Process = orig
        self.assertEqual(calls, [], "有对局在打时不应杀任何进程")

    def test_kills_idle_match_super_between_rooms(self):
        self._patch([111], [])
        import psutil
        killed = []

        class _P:
            def __init__(self, pid):
                self.pid = pid

            def kill(self):
                killed.append(self.pid)

        orig = psutil.Process
        psutil.Process = lambda pid: _P(pid)
        try:
            abctl._kill_idle_match_super()
        finally:
            psutil.Process = orig
        self.assertEqual(killed, [111], "房与房之间应杀掉空闲 match_super 让 A/B 接管")

    def test_noop_when_nothing_running(self):
        self._patch([], [])
        abctl._kill_idle_match_super()      # 不应抛异常


if __name__ == "__main__":
    unittest.main()
