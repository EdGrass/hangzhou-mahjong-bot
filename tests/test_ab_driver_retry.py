# -*- coding: utf-8 -*-
"""A/B 驱动「上一批异常 ⇒ 同臂重跑」单测（_ab_driver.last_batch_bad）。

背景：平台 /api/match 幂等（绝不双房双席）⇒ 上一批崩了而房还在跑时，下一批会被拉回**同一个房**；
若此时换臂就得到"一房两臂"的脏样本（2026-09-16 19:23 实际发生过，两臂各丢一房、读数被污染）。
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("_ab_drv_retry", os.path.join(ROOT, "var", "_ab_driver.py"))
drv = importlib.util.module_from_spec(spec)
sys.modules["_ab_drv_retry"] = drv
spec.loader.exec_module(drv)


def row(ts="2026-09-16 19:23:18", strategy="cand", status="finished", exit_code=0, games=80):
    return {"ts": ts, "strategy": strategy, "status": status, "exit_code": exit_code,
            "ranking": [{"user_id": "u_x", "games_played": games, "total_score": 0}]}


class TestLastBatchBad(unittest.TestCase):
    def _with_rows(self, rows):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.addCleanup(os.unlink, path)
        return path

    def test_clean_room_is_ok(self):
        p = self._with_rows([row()])
        self.assertEqual(drv.last_batch_bad("cand", None, path=p), (False, ""))

    def test_running_snapshot_is_bad(self):
        p = self._with_rows([row(status="running", exit_code=4294967295, games=23)])
        bad, why = drv.last_batch_bad("cand", None, path=p)
        self.assertTrue(bad)
        self.assertEqual(why, "status=running")

    def test_nonzero_exit_is_bad(self):
        p = self._with_rows([row(status="finished", exit_code=1)])
        bad, why = drv.last_batch_bad("cand", None, path=p)
        self.assertTrue(bad)
        self.assertEqual(why, "exit_code=1")

    def test_partial_games_is_bad(self):
        p = self._with_rows([row(status="finished", exit_code=0, games=37)])
        bad, why = drv.last_batch_bad("cand", None, path=p)
        self.assertTrue(bad)
        self.assertEqual(why, "games_played=37")

    def test_no_archive_since_launch_is_bad(self):
        p = self._with_rows([row(ts="2026-09-16 10:00:00")])
        bad, why = drv.last_batch_bad("cand", "2026-09-16 19:00:00", path=p)
        self.assertTrue(bad)
        self.assertEqual(why, "无归档记录")

    def test_other_strategy_rows_ignored(self):
        p = self._with_rows([row(strategy="other", status="running")])
        bad, why = drv.last_batch_bad("cand", None, path=p)
        self.assertTrue(bad)
        self.assertEqual(why, "无归档记录")
