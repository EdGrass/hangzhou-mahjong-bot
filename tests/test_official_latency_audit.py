# -*- coding: utf-8 -*-
"""official_latency_audit 的纯函数测试。"""
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


oa = _load("official_latency_audit_t", "tools/official_latency_audit.py")


class TestAudit(unittest.TestCase):
    def test_percentile(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(oa.percentile(xs, 0.5), 3.0)
        self.assertEqual(oa.percentile(xs, 0.95), 5.0)

    def test_audit_dec_records_splits_draw_and_response(self):
        recs = [
            {"k": "d", "p": "draw", "ms": 100},
            {"k": "d", "p": "draw", "ms": 4000},
            {"k": "d", "p": "draw", "ms": 2000},
            {"k": "d", "p": "response_peng", "ms": 1500},
            {"k": "d", "p": "response_chi", "ms": 100},
            {"k": "e", "p": "draw", "ms": 9999},
        ]
        a = oa.audit_dec_records(recs)
        self.assertEqual(a["draw"]["n"], 3)
        self.assertEqual(a["draw"]["max"], 4000.0)
        self.assertEqual(a["draw"]["over_3000"], 1)
        self.assertEqual(a["response"]["n"], 2)
        self.assertEqual(a["response"]["over_1000"], 1)

    def test_audit_log_lines_counts_warmup_409_timeout(self):
        s = oa.audit_log_lines([
            "预热完成: 50/50 个真实 draw 局面",
            "start bot strategy=speedc151 warmup=50",
            "主循环终止于 API 错误: 409",
            "response timeout 丢窗口",
            "普通日志",
        ])
        self.assertEqual(s["warmup_ok"], 2)
        self.assertEqual(s["http_409"], 1)
        self.assertEqual(s["timeout"], 1)


if __name__ == "__main__":
    unittest.main()
