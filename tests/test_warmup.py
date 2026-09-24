# -*- coding: utf-8 -*-
"""进程内预热与 official keepalive 参数的回归测试。"""
import importlib.util
import io
import json
import os
import sys
import tempfile
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


from bot.warmup import warmup_strategy  # noqa: E402


class _FakePolicy:
    def __init__(self, fail=False):
        self.views = []
        self.fail = fail

    def decide(self, view):
        if self.fail:
            raise RuntimeError("boom")
        self.views.append(view)
        return {"action": "discard", "tile": "1w"}


class TestWarmup(unittest.TestCase):
    def _fixture(self):
        tmp = tempfile.mkdtemp(prefix="warmup_")
        d = os.path.join(tmp, "replays", "auto_20260917_000000")
        os.makedirs(d)
        recs = [
            {"k": "d", "p": "draw", "s": 0, "t": 0,
             "h": ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "2b", "3b", "4b", "5b"],
             "d": "1w", "o": None, "m": [], "r": [], "god": {"b": False, "cc": 0, "p": 0, "cp": False}},
            {"k": "d", "p": "draw", "s": 0, "t": 0,
             "h": ["1w", "1w", "2w", "2w", "3w", "3w", "4w", "4w", "5w", "5w", "6w", "6w", "7w", "东"],
             "d": "1w", "o": None, "m": [], "r": [], "god": {"b": False, "cc": 0, "p": 0, "cp": False}},
            {"k": "d", "p": "response_peng", "s": 0, "t": 0,
             "h": ["1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "2b", "3b"],
             "d": None, "o": "1w", "m": [], "r": [], "god": {}},
        ]
        with io.open(os.path.join(d, "r.dec.jsonl"), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return os.path.join(tmp, "replays")

    def test_zero_disables(self):
        p = _FakePolicy()
        self.assertEqual(warmup_strategy(p, 0, replay_root=self._fixture()), 0)
        self.assertEqual(p.views, [])

    def test_warms_only_draw_records_with_valid_view(self):
        p = _FakePolicy()
        n = warmup_strategy(p, 5, replay_root=self._fixture())
        self.assertEqual(n, 2)
        self.assertEqual(len(p.views), 2)
        for v in p.views:
            self.assertEqual(v["phase"], "draw")
            self.assertEqual(len(v["my_hand"]), 14)
            self.assertEqual(v["drawn_tile"], "1w")

    def test_policy_error_does_not_raise(self):
        p = _FakePolicy(fail=True)
        self.assertEqual(warmup_strategy(p, 5, replay_root=self._fixture()), 0)

    def test_missing_root_is_safe(self):
        p = _FakePolicy()
        self.assertEqual(warmup_strategy(p, 5, replay_root=os.path.join(ROOT, "no_such_dir")), 0)


class TestOfficialWarmupWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ok = _load("official_keepalive_warmup_t", "var/_official_keepalive.py")

    def test_heavy_strategy_gets_warmup(self):
        for s in ("speedc151", "speedc156", "speedc159", "speedc185", "speedc186"):
            self.assertEqual(self.ok.warmup_for_strategy(s), 50, s)

    def test_real_ukeire_family_gets_warmup(self):
        """★ 2026-09-19（R598）：c135/c136/c146 与 c150/c152/c209~c215 全走 real_ukeire
        弃牌路径 —— 漏在 HEAVY_WARMUP 之外会让正式赛以冷缓存开赛（尾延迟 >3s 的历史风险）。
        这条断言把修复锁住；`speedc211` 是当前生产策略。"""
        for s in ("speedc135", "speedc136", "speedc146",
                  "speedc150", "speedc152", "speedc209", "speedc210", "speedc211",
                  "speedc212", "speedc213", "speedc214", "speedc215"):
            self.assertEqual(self.ok.warmup_for_strategy(s), 50, s)

    def test_production_strategy_cmd_has_warmup(self):
        """当前生产策略必须实际带上 --warmup-draws 50。"""
        cmd = self.ok.build_run_bot_cmd("speedc211", "tok", "srv", "log", "rec")
        self.assertIn("--warmup-draws", cmd)
        self.assertEqual(cmd[cmd.index("--warmup-draws") + 1], "50")

    def test_baseline_does_not_get_warmup(self):
        self.assertEqual(self.ok.warmup_for_strategy("speedtugc"), 0)

    def test_build_cmd_includes_warmup_flag(self):
        cmd = self.ok.build_run_bot_cmd("speedc151", "tok", "srv", "log", "rec")
        self.assertIn("--warmup-draws", cmd)
        self.assertEqual(cmd[cmd.index("--warmup-draws") + 1], "50")
        cmd2 = self.ok.build_run_bot_cmd("speedtugc", "tok", "srv", "log", "rec")
        self.assertNotIn("--warmup-draws", cmd2)


if __name__ == "__main__":
    unittest.main()
