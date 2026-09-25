# -*- coding: utf-8 -*-
"""`tools/ab_integrity.py::check_integrity` 的单测 —— 战役读数前的**数据完整性闸门**。

依据（真实事故）：房 `a_0aca4ad1f990` 曾在 `auto_ranking.jsonl` 里有两行、策略不同 ⇒
两臂各丢一房、读数被污染。本工具必须在**每次读数前**把这类脏数据抓出来。
"""
import importlib.util
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


ai = _load("ab_integrity_t", "tools/ab_integrity.py")
ARMS = ["speedtugc", "speedc152"]


def row(room, strat, ts="2026-09-17 01:00:00", status="finished", exit_code=0):
    return {"room": room, "strategy": strat, "ts": ts, "status": status, "exit_code": exit_code}


class TestAbIntegrity(unittest.TestCase):
    def test_clean(self):
        rows = [row("a_1", "speedtugc"), row("a_2", "speedc152"), row("a_3", "speedtugc")]
        ok, rep = ai.check_integrity(rows, "2026-09-17 00:00:00", ARMS)
        self.assertTrue(ok)
        self.assertEqual(rep["rooms"], 3)
        self.assertEqual(rep["per_arm"], {"speedtugc": 2, "speedc152": 1})

    def test_duplicate_room_flagged(self):
        """同一房两行（无论策略是否相同）都必须报出来——真实事故就是这种形状。"""
        rows = [row("a_1", "speedtugc"), row("a_1", "speedc152")]
        ok, rep = ai.check_integrity(rows, "", ARMS)
        self.assertFalse(ok)
        self.assertEqual(rep["dup_rows"], {"a_1": 2})
        self.assertEqual(rep["multi_strategy"], {"a_1": ["speedc152", "speedtugc"]})

    def test_unknown_strategy_flagged(self):
        rows = [row("a_1", "speedtugc"), row("a_2", "speedc999")]
        ok, rep = ai.check_integrity(rows, "", ARMS)
        self.assertFalse(ok)
        self.assertEqual(rep["unknown_strategies"], {"speedc999": 1})

    def test_not_finished_and_bad_exit_flagged(self):
        rows = [row("a_1", "speedtugc", status="running"), row("a_2", "speedc152", exit_code=4294967295)]
        ok, rep = ai.check_integrity(rows, "", ARMS)
        self.assertFalse(ok)
        self.assertEqual(rep["not_finished"], ["a_1"])
        self.assertEqual(rep["bad_exit"], [("a_2", 4294967295)])

    def test_since_filters(self):
        rows = [row("a_old", "speedtugc", ts="2026-09-16 10:00:00"),
                row("a_new", "speedtugc", ts="2026-09-17 10:00:00")]
        ok, rep = ai.check_integrity(rows, "2026-09-17 00:00:00", ARMS)
        self.assertTrue(ok)
        self.assertEqual(rep["rooms"], 1)

    def test_no_arms_means_skip_strategy_check(self):
        rows = [row("a_1", "whatever")]
        ok, rep = ai.check_integrity(rows, "", [])
        self.assertTrue(ok)

    # ---- 跨役残留（2026-09-17 真实故障：这条误报会让 19:00 的正式赛切换被拒绝执行）----

    def test_cross_campaign_residue_not_an_error(self):
        """旧役最后一房：**开房早于本役 started**、结果落在 started 之后。
        它策略不在本役臂列表里，但**不是污染** ⇒ 必须只作提示，不参与 ok。"""
        rows = [row("a_old", "speedc164", ts="2026-09-17 11:34:41"),
                row("a_new", "speedtugc", ts="2026-09-17 11:50:00")]
        starts = {"a_old": "2026-09-17 11:19:50", "a_new": "2026-09-17 11:34:53"}
        ok, rep = ai.check_integrity(rows, "2026-09-17 11:22:11", ARMS, starts)
        self.assertTrue(ok, "跨役残留被误判成异常：%s" % rep)
        self.assertEqual(rep["unknown_strategies"], {})
        self.assertEqual(rep["rooms"], 1)
        self.assertEqual(rep["residue"], [("a_old", "speedc164", "2026-09-17 11:19:50")])

    def test_unknown_strategy_after_since_still_flagged(self):
        """开房在本役之内、策略却不在臂列表 ⇒ 仍然是硬错误（不能一起放过）。"""
        rows = [row("a_bad", "speedc999", ts="2026-09-17 12:00:00")]
        starts = {"a_bad": "2026-09-17 11:57:00"}
        ok, rep = ai.check_integrity(rows, "2026-09-17 11:22:11", ARMS, starts)
        self.assertFalse(ok)
        self.assertEqual(rep["unknown_strategies"], {"speedc999": 1})

    def test_missing_start_info_stays_conservative(self):
        """定位不到开房时刻的房 —— 宁可保守：仍按本役处理（照旧报未知策略）。"""
        rows = [row("a_unknown_time", "speedc999", ts="2026-09-17 12:00:00")]
        ok, rep = ai.check_integrity(rows, "2026-09-17 11:22:11", ARMS, {})
        self.assertFalse(ok)

    def test_room_start_times_from_real_replays(self):
        """开房时刻表必须能覆盖 auto_ranking 里的房（否则本机制形同虚设）。"""
        starts = ai.room_start_times()
        if not starts:
            self.skipTest("无复盘目录")
        for r in ai.load_rows()[-30:]:
            room = r.get("room")
            if room:
                self.assertIn(room, starts, "房 %s 定位不到开房时刻" % room)


    def test_short_replays_older_than_stale_flagged(self):
        """★ R1526：每房应 10 份复盘；超过时限仍不齐 ⇒ **异常**（会偏低该臂房级指标）。"""
        rows = [row("a_1", "speedtugc", ts="2026-09-17 01:00:00")]
        ok, rep = ai.check_integrity(rows, "", ARMS, replay_counts={"a_1": 3},
                                     now="2026-09-17 02:00:00")
        self.assertFalse(ok)
        self.assertEqual([("a_1", "speedtugc", 3)], rep["short_replays"])
        self.assertEqual([], rep["late_replays"])

    def test_fresh_room_not_yet_fetched_is_not_flagged(self):
        """刚结束 <30min 的房复盘未齐 = 抓取延迟（预期），**不计异常**。"""
        rows = [row("a_1", "speedtugc", ts="2026-09-17 01:55:00")]
        ok, rep = ai.check_integrity(rows, "", ARMS, replay_counts={"a_1": 0},
                                     now="2026-09-17 02:00:00")
        self.assertTrue(ok)
        self.assertEqual([("a_1", 0)], rep["late_replays"])
        self.assertEqual([], rep["short_replays"])

    def test_full_replays_clean(self):
        rows = [row("a_1", "speedtugc", ts="2026-09-17 01:00:00"),
                row("a_2", "speedc152", ts="2026-09-17 01:10:00")]
        ok, rep = ai.check_integrity(rows, "", ARMS,
                                     replay_counts={"a_1": 10, "a_2": 10},
                                     now="2026-09-17 02:00:00")
        self.assertTrue(ok)
        self.assertEqual([], rep["short_replays"])
        self.assertEqual([], rep["late_replays"])


if __name__ == "__main__":
    unittest.main()
