# -*- coding: utf-8 -*-
"""★ 2026-09-16 新增：**非完成房 / 一房两臂**都不得计入臂。

两次实测事故：
① 19:23:18 一次离线重放 OOM 杀掉了候选臂的 run_bot，该房以
   `status=running / exit_code=4294967295 / games_played=23` 落盘（**半房快照**）；
② 驱动排下一批时 `/api/match` **幂等返回同一个房**（平台"绝不双房双席"）⇒
   这一房**前 23 手是候选臂打的、后 57 手是基线臂打的**（同房 id 出现两个策略）。
旧口径把①当成"真实的候选臂房"，把 c151 的净胜/房从 −22.9 抬到 +18.4、t 从 0.60 抬到 1.12。
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ab_readout as rd          # noqa: E402

ME = rd.ME


def _row(ts, room, status, exit_code, games, strategy="t", mine_score=0.0):
    rk = [{"user_id": ME, "total_score": mine_score, "rank": 1, "games_played": games}]
    for i in range(3):
        rk.append({"user_id": "u_other%d" % i, "total_score": 0, "rank": i + 2, "games_played": games})
    return {"ts": ts, "room": room, "strategy": strategy, "status": status,
            "exit_code": exit_code, "ranking": rk}


def _write(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


class TestInvalidRoomsExcluded(unittest.TestCase):
    def _with_ranking(self, rows):
        path = _write(rows)
        orig = rd.RANKING
        rd.RANKING = path
        rd.INVALID.clear()
        self.addCleanup(lambda: (setattr(rd, "RANKING", orig), rd.INVALID.clear(), os.unlink(path)))

    def test_only_finished_80game_room_counts(self):
        self._with_ranking([
            _row("2026-09-16 10:00:00", "a_r1", "finished", 0, 80, mine_score=40),
            _row("2026-09-16 11:00:00", "a_r2", "running", 4294967295, 23, mine_score=12),  # 崩溃半房
            _row("2026-09-16 12:00:00", "a_r3", "finished", 1, 80, mine_score=40),           # 退出码非 0
            _row("2026-09-16 13:00:00", "a_r4", "finished", 0, 37, mine_score=40),           # 局数不足
        ])
        got = rd.rooms_for("t")
        self.assertEqual(len(got), 1)
        self.assertEqual(len(rd.INVALID), 3)

    def test_same_room_two_strategies_excluded_from_both(self):
        """一房两臂（崩溃后被下一臂接管）⇒ **两臂都不算**。"""
        self._with_ranking([
            _row("2026-09-16 19:23:18", "a_mix", "running", 4294967295, 23, "cand", mine_score=12),
            _row("2026-09-16 19:33:03", "a_mix", "finished", 0, 80, "base", mine_score=-18),
            _row("2026-09-16 19:47:16", "a_ok", "finished", 0, 80, "cand", mine_score=50),
        ])
        self.assertEqual([r["room"] for r in rd.rooms_for("cand")], ["a_ok"])
        self.assertEqual(rd.rooms_for("base"), [])
        self.assertEqual(rd.INVALID[("2026-09-16 19:23:18", "a_mix")], "status=running")
        self.assertEqual(rd.INVALID[("2026-09-16 19:33:03", "a_mix")], "multi-strategy")

    def test_since_with_iso_T_is_normalized_not_silently_dropped(self):
        """★ R1551：`--since` 写成 ISO 形式（带 `T`）**不能静默丢掉当天全部房**。

        为什么单独钉：台账的 ts 是 ``2026-09-20 14:54:07``（空格），而 ``" " < "T"``
        ⇒ 拿 ISO 形式去比会判成“大于当天所有行”，静默得出一个**偏小的房集**。
        2026-09-21 实测：带 `T` 报 30/29 房，空格形式报真实的 46/46。
        此处只钉“两种写法房集相等”—— 它是静默的，不钉就会再犯。
        """
        self._with_ranking([
            _row("2026-09-20 14:54:07", "a_t1", "finished", 0, 80, mine_score=10),
            _row("2026-09-20 15:10:00", "a_t2", "finished", 0, 80, mine_score=20),
            _row("2026-09-19 23:59:59", "a_before", "finished", 0, 80, mine_score=30),
        ])
        sp = [r["room"] for r in rd.rooms_for("t", since="2026-09-20 14:54:07")]
        iso = [r["room"] for r in rd.rooms_for("t", since="2026-09-20T14:54:07")]
        self.assertEqual(sp, iso, u"ISO 形式被静默丢数据了")
        self.assertEqual(["a_t1", "a_t2"], sorted(iso))

    def test_norm_since_edges(self):
        self.assertIsNone(rd._norm_since(None))
        self.assertIsNone(rd._norm_since(""))
        self.assertEqual("2026-09-20 14:54:07", rd._norm_since(" 2026-09-20T14:54:07 "))


    def test_arm_rooms_from_log_also_excludes(self):
        """按排批归属的那条路径（arm_rooms_from_log）同样要排掉。**不碰真文件**。"""
        self._with_ranking([
            _row("2026-09-16 10:00:00", "a_r1", "finished", 0, 80, mine_score=40),
            _row("2026-09-16 11:00:00", "a_r2", "running", 4294967295, 23, mine_score=12),
        ])
        fd, tmp = tempfile.mkstemp(suffix="_ablog.jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for ts in ("2026-09-16 09:59:00", "2026-09-16 10:59:00"):
                f.write(json.dumps({"ts": ts, "arm": "a", "strategy": "t"}) + "\n")
        try:
            out = rd.arm_rooms_from_log(None, log_path=tmp)
        finally:
            os.unlink(tmp)
        self.assertEqual(len(out.get("t", [])), 1)
