"""window_audit 夹具测试：N 日志按 gid 配对 → δ/CI/裁决。"""
import json
import os
import tempfile
import unittest

from tools.window_audit import audit_logs, parse_log


def _make_log(path, strat, gid_scores):
    """gid_scores: {gid: (seat, [s0,s1,s2,s3])}（每 gid 数组须零和）"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("[00:00:00] 策略: %s\n" % strat)
        for gid, (seat, scores) in sorted(gid_scores.items()):
            f.write("[00:00:01] 本场结束: finished 标记（gid=%s）\n" % gid)
            f.write("[00:00:01] 本场积分 seat=%d: %s\n" % (seat, json.dumps(scores)))


class TestParseLog(unittest.TestCase):
    def test_parse(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "a.log")
            _make_log(p, "speedE", {"g1": (0, [-8, -1, -1, 10])})
            strat, recs = parse_log(p)
            self.assertEqual(strat, "speedE")
            self.assertEqual(recs["g1"], (0, [-8, -1, -1, 10]))


class TestAuditLogs(unittest.TestCase):
    def test_same_table_pairing(self):
        with tempfile.TemporaryDirectory() as td:
            pa = os.path.join(td, "h.log")
            pe = os.path.join(td, "e.log")
            # 每局候选席与基准席同值 → 配对差恰为 0；两局座位轮换
            _make_log(pa, "speedh",
                      {"g1": (0, [10, 10, -8, -12]),
                       "g2": (2, [-8, -12, 10, 10])})
            _make_log(pe, "speedE",
                      {"g1": (1, [10, 10, -8, -12]),
                       "g2": (3, [-8, -12, 10, 10])})
            res = audit_logs([{"name": "h", "path": pa},
                              {"name": "e", "path": pe}])
            self.assertEqual(res["n"], 2)
            self.assertAlmostEqual(res["delta"], 0.0, places=9)
            self.assertEqual(res["verdict"], "DRAW")


if __name__ == "__main__":
    unittest.main()
