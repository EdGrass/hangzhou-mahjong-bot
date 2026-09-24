# -*- coding: utf-8 -*-
"""`tools/real_game_audit.py::work` 对**非复盘文件**的容错单测。

真实缺陷（2026-09-17 赛前预演）：`fetch_tournament_replays.py` 会在输出目录里写一个
`manifest.json`（内容是 JSON **list**），而审计工具 `--dirs <dir>` 会 glob `*.json` 并直接
`d.get("seats")` ⇒ **AttributeError 崩掉整个审计**（今晚 21:30 的第 ② 步就会踩）。
本测试钉住：非 dict 的 JSON ⇒ `work()` 返回 None（跳过），不抛异常。
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
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


rga = _load("rga_t", "tools/real_game_audit.py")


class TestAuditSkipsNonReplay(unittest.TestCase):
    def _tmp(self, obj):
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        self.addCleanup(os.unlink, p)
        return p

    def test_list_json_returns_none(self):
        self.assertIsNone(rga.work(self._tmp([{"a": 1}])), "manifest.json 这种 list 必须被跳过")

    def test_scalar_json_returns_none(self):
        self.assertIsNone(rga.work(self._tmp("nope")))

    def test_missing_file_returns_none(self):
        self.assertIsNone(rga.work(os.path.join(ROOT, "var", "replays", ".no_such.json")))

    def test_dict_without_seats_returns_none(self):
        self.assertIsNone(rga.work(self._tmp({"blocks": []})))


if __name__ == "__main__":
    unittest.main()
