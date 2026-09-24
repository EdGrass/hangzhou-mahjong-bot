# -*- coding: utf-8 -*-
"""看门狗决策单测：覆盖导致 09-14 长时间停机的「双缺」路径。"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location(
    "wd", os.path.join(ROOT, "var", "_watchdog.py"))
wd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wd)


class TestWatchdogDecide(unittest.TestCase):
    def test_rotate_on_repeated_match_failures(self):
        self.assertEqual(wd.decide_action(1, 1, 3, 0), ("rotate", 0))

    def test_kill_supervisor_when_it_has_no_child(self):
        self.assertEqual(wd.decide_action(1, 0, 0, 0), ("kill_ms", 0))

    def test_nothing_while_a_game_is_plausibly_running(self):
        self.assertEqual(wd.decide_action(1, 1, 0, 0), ("none", 0))

    def test_dual_absence_counts_up_then_restarts_keeper(self):
        """回归：09-14 停机 —— match_super 与 run_bot 都不在时必须最终重启 keeper，
        旧代码在此路径永远返回「暂不动作」，导致 10 小时无人自愈。"""
        streak = 0
        actions = []
        for _ in range(wd.NOCHILD_NEED):
            act, streak = wd.decide_action(0, 0, 0, streak)
            actions.append(act)
        self.assertEqual(actions[-1], "restart_kpr")
        self.assertTrue(all(a == "none" for a in actions[:-1]),
                        "在达到阈值前不应动作，给 keeper 的正常 120s 巡检留出窗口")
        self.assertEqual(streak, 0)

    def test_streak_resets_when_processes_reappear(self):
        """正常批次间隙会让进程短暂缺席：一旦进程回来必须重新计数。"""
        act, streak = wd.decide_action(0, 0, 0, 0)
        self.assertEqual((act, streak), ("none", 1))
        act, streak = wd.decide_action(1, 1, 0, streak)      # 进程回来了
        self.assertEqual((act, streak), ("none", 0))
        act, streak = wd.decide_action(0, 0, 0, streak)      # 重新开始计数
        self.assertEqual((act, streak), ("none", 1))


if __name__ == "__main__":
    unittest.main()
