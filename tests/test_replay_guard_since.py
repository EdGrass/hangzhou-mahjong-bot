# -*- coding: utf-8 -*-
"""`var/_replay_guard.default_since` \u7684\u5355\u6d4b\uff1a\u9ed8\u8ba4\u53ea\u8865**\u5f53\u524d\u6218\u5f79**\u7684\u590d\u76d8\u3002

\u4e3a\u4ec0\u4e48\uff1a\u65e7\u5b9e\u73b0\u628a\u5f79 2 \u8d77\u70b9\u5199\u6210\u9ed8\u8ba4\uff0c\u800c\u8ba1\u5212\u4efb\u52a1\u4e0d\u4f20\u53c2 \u21d2 \u4e0b\u4e00\u5f79\u4f1a\u201c\u53ea\u8865\u65e7\u623f\u3001
\u65b0\u623f\u6c38\u8fdc\u4e0d\u8865\u201d \u21d2 \u5224\u8bcd\u56e0\u8986\u76d6\u7387\u4e0d\u8db3\u800c REFUSE\u3002\u672c\u5355\u6d4b\u628a\u201c\u8ddf\u968f .ab_mode\u201d\u4e0e\u201c\u8bfb\u4e0d\u5230\u624d\u56de\u9000\u201d\u4e24\u4ef6\u4e8b\u9489\u6b7b\u3002
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _replay_guard as G  # noqa: E402


class TestReplayGuardSince(unittest.TestCase):
    def test_follows_ab_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ab.json")
            with io.open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"started": "2026-09-30 12:00:00"}))
            self.assertEqual("2026-09-30 12:00:00", G.default_since(p))

    def test_fallback_when_missing(self):
        self.assertEqual(G.DEFAULT_SINCE, G.default_since(os.path.join(tempfile.gettempdir(), "nope_xyz.json")))

    def test_fallback_when_garbage(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bad.json")
            with io.open(p, "w", encoding="utf-8") as fh:
                fh.write("not-json")
            self.assertEqual(G.DEFAULT_SINCE, G.default_since(p))

    def test_fallback_when_started_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "empty.json")
            with io.open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"started": ""}))
            self.assertEqual(G.DEFAULT_SINCE, G.default_since(p))


if __name__ == "__main__":
    unittest.main()