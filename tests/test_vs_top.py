# -*- coding: utf-8 -*-
"""`tools/vs_top.py` 的单测：**同房头对头**这把尺子的口径不变量（STATUS §9.99）。

关键不变量：
  ① `pair_rows` 只在**同一房**内配对，且只收参照名单里的对手；
  ② 同一房命中多个参照对象时 `one_per_room` 只留**分最高**的一个（保证每房一条、配对独立）；
  ③ `summary` 的差 = 他们 − 我们；胜率 = "他们分更高"的比例；t 用 pairs 的配对 SD；
  ④ 没有共房时返回 `{"n": 0}`（不能抛异常、不能给出假读数）。
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
    spec.loader.exec_module(m)
    return m


vt = _load("vs_top_t", "tools/vs_top.py")
ME = "u_me"
TOP = "u_top"


def _room(room, ts, me_score, me_rank, top_score, top_rank, others=()):
    rk = [{"user_id": ME, "total_score": me_score, "rank": me_rank},
          {"user_id": TOP, "total_score": top_score, "rank": top_rank}]
    for i, (u, sc, r) in enumerate(others):
        rk.append({"user_id": u, "total_score": sc, "rank": r})
    return {"room": room, "ts": ts, "status": "finished", "ranking": rk}


class TestVsTop(unittest.TestCase):
    def test_pair_rows_same_room_only(self):
        rows = [
            _room("a_1", "2026-09-16 10:00:00", 10, 1, -10, 2),
            {"room": "a_2", "ts": "2026-09-16 11:00:00", "status": "finished",
             "ranking": [{"user_id": TOP, "total_score": 99, "rank": 1},          # 我们不在场
                         {"user_id": "u_x", "total_score": 0, "rank": 2}]},
            {"room": "a_3", "ts": "2026-09-16 12:00:00", "status": "running",      # 未完房
             "ranking": [{"user_id": ME, "total_score": 1, "rank": 1},
                         {"user_id": TOP, "total_score": 0, "rank": 2}]},
        ]
        p = vt.pair_rows(rows, ME, [TOP])
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0][0], TOP)
        self.assertEqual(p[0][1], -10.0)     # 他们
        self.assertEqual(p[0][3], 10.0)      # 我们
        self.assertEqual(p[0][5], "2026-09-16")

    def test_pair_rows_ignores_non_listed(self):
        rows = [_room("a_1", "2026-09-16 10:00:00", 1, 1, 2, 2,
                      others=[("u_other", 500, 1)])]
        self.assertEqual(len(vt.pair_rows(rows, ME, [TOP])), 1)
        self.assertEqual(len(vt.pair_rows(rows, ME, ["u_other"])), 1)
        self.assertEqual(len(vt.pair_rows(rows, ME, ["u_nobody"])), 0)

    def test_one_per_room_keeps_strongest(self):
        rows = [_room("a_1", "2026-09-16 10:00:00", 0, 3, 50, 1,
                      others=[("u_top2", 90, 1)])]
        p = vt.pair_rows(rows, ME, [TOP, "u_top2"])
        self.assertEqual(len(p), 2)
        kept = vt.one_per_room(p)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0][0], "u_top2")     # 分更高者留下
        self.assertEqual(kept[0][1], 90.0)

    def test_summary_direction_and_winrate(self):
        pairs = [(TOP, 100.0, 1, -50.0, 4, "2026-09-16", "a_1"),
                 (TOP, -20.0, 3, 10.0, 1, "2026-09-16", "a_2")]
        s = vt.summary(pairs)
        self.assertEqual(s["n"], 2)
        self.assertEqual(s["diff"], 60.0)          # (150 + (-30)) / 2
        self.assertEqual(s["top_mean"], 40.0)
        self.assertEqual(s["my_mean"], -20.0)
        self.assertEqual(s["win_rate"], 0.5)       # 第一房他们高、第二房我们高
        self.assertEqual(s["top_first"], 0.5)
        self.assertEqual(s["my_first"], 0.5)

    def test_summary_empty(self):
        self.assertEqual(vt.summary([]), {"n": 0})


if __name__ == "__main__":
    unittest.main()
