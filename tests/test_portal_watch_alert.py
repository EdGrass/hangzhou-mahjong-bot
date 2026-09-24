# -*- coding: utf-8 -*-
"""`var/_portal_watch.alert_on_change` \u7684\u5355\u6d4b\uff08\u7eaf\u51fd\u6570\uff0c\u65e0\u7f51\u7edc\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u201c\u4e0d\u8981\u9519\u8fc7\u62a5\u540d\u622a\u6b62\u201d\u662f**\u771f\u5b9e\u6559\u8bad**\uff08\u56db\u6d4b\u662f\u5076\u7136\u67e5\u95e8\u6237\u624d\u53d1\u73b0\u7684\uff0c\u5f53\u65f6\u8ddd\u622a\u6b62 ~5h\uff09\u3002
\u65b0\u589e\u7684\u843d\u76d8\u544a\u8b66\u5fc5\u987b\u88ab\u5355\u6d4b\u9489\u6b7b\uff0c\u5426\u5219\u5230 10/10 \u53c8\u4f1a\u53d8\u6210\u201c\u65e5\u5fd7\u91cc\u6709\u4e00\u884c\u6ca1\u4eba\u770b\u201d\u3002
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _portal_watch as pw  # noqa: E402


def _snap(ids, anns=(), my_registered=True):
    return {
        "ts": "2026-10-01 12:00:00",
        "tournaments": [
            {"id": i, "name": "evt-%s" % i, "status": "registering",
             "start_at": 1791000000, "register_deadline": 1790999000,
             "registered": 10, "my_registered": my_registered}
            for i in ids
        ],
        "announcement_ids": list(anns),
    }


class TestPortalAlert(unittest.TestCase):
    def test_no_prev_no_alert(self):
        nt, na, urgent, rows = pw.alert_on_change({}, _snap(["t_1"]))
        self.assertEqual([], nt)
        self.assertEqual([], na)
        self.assertEqual([], urgent)
        self.assertEqual([], rows)

    def test_new_event_detected(self):
        nt, na, urgent, rows = pw.alert_on_change(_snap(["t_1"]), _snap(["t_1", "t_2"]))
        self.assertEqual(["t_2"], nt)
        self.assertEqual(1, len(rows))
        self.assertEqual("t_2", rows[0]["id"])

    def test_urgent_when_not_registered_and_deadline_soon(self):
        now = 1790999000 - 3600          # \u8ddd\u622a\u6b62 1 \u5c0f\u65f6
        nt, na, urgent, rows = pw.alert_on_change(_snap(["t_1"]), _snap(["t_1", "t_2"], my_registered=False),
                                                 now_ts=now)
        self.assertEqual(["t_2"], nt)
        self.assertTrue(urgent and "t_2" in urgent[0])

    def test_not_urgent_when_already_registered(self):
        now = 1790999000 - 3600
        nt, na, urgent, rows = pw.alert_on_change(_snap(["t_1"]), _snap(["t_1", "t_2"], my_registered=True),
                                                  now_ts=now)
        self.assertEqual(["t_2"], nt)
        self.assertEqual([], urgent)

    def test_new_announcement_detected(self):
        nt, na, urgent, rows = pw.alert_on_change(_snap(["t_1"], anns=["a1"]),
                                                  _snap(["t_1"], anns=["a1", "a2"]))
        self.assertEqual([], nt)
        self.assertEqual(["a2"], na)


if __name__ == "__main__":
    unittest.main()