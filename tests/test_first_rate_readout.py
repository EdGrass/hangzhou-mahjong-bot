# -*- coding: utf-8 -*-
"""`tools/first_rate_readout.py` 的契约单测。

要钉住的四件事（都直接决定"能不能拿它当判据"）：
  ① **同窗口过滤**：只在 `ts >= since` 且 `status=finished` 的房里统计，臂必须命中白名单；
  ② **第一率/末位率/均分** 的定义（rank==1 / rank==4 / total_score 均值）；
  ③ **两比例 z** 的方向与量级（候选 − 基线）；
  ④ **分辨力公式**：delta 越小需要的房越多（单调），且 5.4pp 对应 ~500 房/臂量级
     —— 这条是"为什么不能用 80 房的第一率做判词"的**定量依据**。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_me"
_spec = importlib.util.spec_from_file_location("frr", os.path.join(ROOT, "tools", "first_rate_readout.py"))
frr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frr)


def _room(ts, arm, my_rank, my_score, me=ME):
    return {"ts": ts, "room": "r_%s_%s" % (arm, ts), "strategy": arm, "status": "finished",
            "ranking": [{"user_id": me, "rank": my_rank, "total_score": my_score},
                        {"user_id": "u_x", "rank": 7 - my_rank, "total_score": -my_score}]}


class TestFirstRateReadout(unittest.TestCase):
    def _ledger(self, rows):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.addCleanup(os.unlink, p)
        return p

    def test_summarize_definitions(self):
        items = [("t1", "a", {"rank": 1, "total_score": 100}),
                 ("t2", "a", {"rank": 4, "total_score": -50}),
                 ("t3", "a", {"rank": 1, "total_score": 50})]
        s = frr.summarize(items)["a"]
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["first_rate"], 2 / 3)
        self.assertAlmostEqual(s["last_rate"], 1 / 3)
        self.assertAlmostEqual(s["mean"], 100 / 3)
        self.assertAlmostEqual(s["mean_rank"], 2.0)

    def test_load_filters_since_status_arm_me(self):
        rows = [
            _room("2026-09-23 03:00:00", "a", 1, 10),          # 早于 since
            _room("2026-09-23 04:00:00", "a", 1, 10),
            _room("2026-09-23 05:00:00", "b", 4, -10),
            _room("2026-09-23 06:00:00", "c", 1, 10),          # 不在白名单
            dict(_room("2026-09-23 07:00:00", "a", 1, 10), status="running"),   # 未结束
            _room("2026-09-23 08:00:00", "a", 1, 10, me="u_other"),             # 不是我们
        ]
        p = self._ledger(rows)
        got = frr.load(p, "2026-09-23 03:30:00", ("a", "b"), ME)
        self.assertEqual([(x[0], x[1]) for x in got], [("2026-09-23 04:00:00", "a"),
                                                      ("2026-09-23 05:00:00", "b")])

    def test_load_all_arms_when_empty(self):
        p = self._ledger([_room("2026-09-23 04:00:00", "a", 1, 10),
                          _room("2026-09-23 05:00:00", "z", 4, -10)])
        self.assertEqual(len(frr.load(p, "", (), ME)), 2)

    def test_first_rate_z_direction(self):
        # 候选 30/100 vs 基线 20/100 ⇒ 正；反过来则负
        z1, se1 = frr.first_rate_z(0.20, 100, 0.30, 100)
        z2, _ = frr.first_rate_z(0.30, 100, 0.20, 100)
        self.assertGreater(z1, 0)
        self.assertLess(z2, 0)
        self.assertAlmostEqual(z1, -z2)
        self.assertGreater(se1, 0)
        # 样本量四倍 ⇒ SE 半归一化
        _, se2 = frr.first_rate_z(0.20, 400, 0.30, 400)
        self.assertAlmostEqual(se2, se1 / 2, places=6)

    def test_rooms_needed_monotone_and_scale(self):
        big = frr.rooms_needed(0.10)
        mid = frr.rooms_needed(0.054)
        small = frr.rooms_needed(0.02)
        self.assertLess(big, mid)
        self.assertLess(mid, small)
        self.assertTrue(400 < mid < 600, mid)          # 5.4pp ⇒ ~500 房/臂 量级
        self.assertIsNone(frr.rooms_needed(0.0))       # 无差异 ⇒ 不给上限
        self.assertIsNone(frr.rooms_needed(-0.05))

    def test_ab_ctx_reads_arms_and_since(self):
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": "speedc151", "b": "speedvalue",
                                "arms": ["speedc151", "speedvalue"], "started": "2026-09-23 03:13:44"}))
        self.addCleanup(os.unlink, p)
        arms, since = frr.ab_ctx(p)
        self.assertEqual(arms, ["speedc151", "speedvalue"])
        self.assertEqual(since, "2026-09-23 03:13:44")
        self.assertEqual(frr.ab_ctx(os.path.join(ROOT, "var", ".no_such_ab")), ([], ""))

    def test_cli_on_synthetic_ledger(self):
        p = self._ledger([_room("2026-09-23 04:00:00", "a", 1, 100),
                          _room("2026-09-23 05:00:00", "a", 4, -100),
                          _room("2026-09-23 06:00:00", "b", 1, 50),
                          _room("2026-09-23 07:00:00", "b", 1, 50)])
        out = subprocess.run([sys.executable, "-X", "utf8",
                              os.path.join(ROOT, "tools", "first_rate_readout.py"),
                              "--ledger", p, "--since", "", "--arms", "a,b", "--me", ME],
                             capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        s = out.stdout
        self.assertIn("50.0%", s)      # a 的第一率
        self.assertIn("100.0%", s)     # b 的第一率
        self.assertIn("_gate2.py", s)  # 口径提醒必须在

    def test_cli_no_rows_exits_2(self):
        p = self._ledger([])
        out = subprocess.run([sys.executable, "-X", "utf8",
                              os.path.join(ROOT, "tools", "first_rate_readout.py"),
                              "--ledger", p, "--since", "", "--arms", "nope"],
                             capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
