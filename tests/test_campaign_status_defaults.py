# -*- coding: utf-8 -*-
"""★ R1577：`var/_campaign_status.py` 的**默认值必须来自当前役**（`.ab_mode`）。

为什么：它是 HANDOFF 里叫人跑的“一屏总览”，而旧默认写死成**役2**
（`2026-09-23 03:13:44` / `speedc151` vs `speedvalue`）⇒ 无参跑会打印役2 的“✅ 可判决 / ADOPT speedvalue”，
读者会以为**当前役**已有结论（工具在说谎）。
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
import _campaign_status as C  # noqa: E402


def _write(cfg):
    d = tempfile.mkdtemp(prefix="r1577_")
    p = os.path.join(d, ".ab_mode")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(cfg))
    return p


class TestAbDefaults(unittest.TestCase):
    def test_n_arm(self):
        d = C.ab_defaults(_write({"arms": ["base", "b", "c"], "bundles": ["base"], "started": "T"}))
        self.assertEqual("base", d["baseline"])
        self.assertEqual(["b", "c"], d["candidates"])
        self.assertEqual("T", d["since"])

    def test_legacy_two_arm(self):
        d = C.ab_defaults(_write({"a": "x", "b": "y"}))
        self.assertEqual("x", d["baseline"])
        self.assertEqual(["y"], d["candidates"])

    def test_degenerate_returns_none(self):
        self.assertIsNone(C.ab_defaults(_write({"arms": ["only"], "bundles": ["only"]})))
        self.assertIsNone(C.ab_defaults(_write({})))
        self.assertIsNone(C.ab_defaults(os.path.join(tempfile.gettempdir(), "no_such_ab_mode.json")))

    def test_live_mode_wins_over_hardcoded_han2(self):
        """真机：有 `.ab_mode` 时，默认值**必须**等于它——这就是本修的目的。"""
        p = os.path.join(ROOT, "var", ".ab_mode")
        if not os.path.exists(p):
            self.skipTest("无 .ab_mode（役已收口或 var/ 不在）")
        with io.open(p, encoding="utf-8-sig") as f:
            cfg = json.loads(f.read())
        d = C.ab_defaults()
        self.assertIsNotNone(d)
        self.assertEqual(cfg.get("started"), d["since"])
        self.assertEqual(str((cfg.get("bundles") or ["?"])[0]), d["baseline"])
        for a in (cfg.get("arms") or [cfg.get("a"), cfg.get("b")]):
            if a:
                self.assertIn(a, d["arms"])
        self.assertNotEqual(("speedc151", "speedvalue"), (d["baseline"], d["candidates"][0]),
                            "不能回到写死的役2 组合")
