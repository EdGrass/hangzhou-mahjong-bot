# -*- coding: utf-8 -*-
"""★ R1542：`_bsegment` 对“**本役已经切过**”必须幂等。

为什么必须钉：`_adopt_pair` 每 10 分钟重试。若第 4 步切役成功、而第 5 步
（**注册判词看护**）失败，旧实现的重试会**重跑整个 B 段** ⇒ 用新的起役时间戳再切一次
⇒ 已打的房全部作废，而且**每 10 分钟无限重切**（永远攒不满 80 房 ⇒ 判词到不了）。
本文件只钉纯函数与源码顺序（不动任何真实状态）。
"""
from __future__ import annotations
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))


def _load():
    spec = importlib.util.spec_from_file_location("bseg_t", os.path.join(ROOT, "var", "_bsegment.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["bseg_t"] = m
    spec.loader.exec_module(m)
    return m


g = _load()


class TestParseSwitched(unittest.TestCase):
    def test_reads_three_fields(self):
        d = g.parse_switched("ts=2026-09-29 03:00:00 base=speedvaluebc cands=speedvaluebcmeldp45\n")
        self.assertEqual("2026-09-29", d["ts"][:10])
        self.assertEqual("speedvaluebc", d["base"])
        self.assertEqual("speedvaluebcmeldp45", d["cands"])

    def test_empty(self):
        self.assertEqual({}, g.parse_switched(""))
        self.assertEqual({}, g.parse_switched(None))


class TestAlreadySwitched(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.ab = os.path.join(self.d.name, ".ab_mode")
        self.mk = os.path.join(self.d.name, ".bsegment_switched_yaku4")

    def tearDown(self):
        self.d.cleanup()

    def _ab(self, started, arms, bundles):
        with io.open(self.ab, "w", encoding="utf-8") as f:
            json.dump({"started": started, "arms": arms, "bundles": bundles}, f)

    def _mark(self, text):
        with io.open(self.mk, "w", encoding="utf-8") as f:
            f.write(text)

    def test_no_marker(self):
        self._ab("2026-09-29 03:00:00", ["speedvaluebc", "speedvaluebcmeldp45"], ["speedvaluebc"])
        self.assertFalse(g.already_switched("yaku4", self.mk, self.ab)[0])

    def test_ts_match_counts_as_done(self):
        self._ab("2026-09-29 03:00:00", ["speedvaluebc", "speedvaluebcmeldp45"], ["speedvaluebc"])
        self._mark("ts=2026-09-29 03:00:00 base=speedvaluebc cands=speedvaluebcmeldp45\n")
        done, ts, why = g.already_switched("yaku4", self.mk, self.ab)
        self.assertTrue(done, why)
        self.assertEqual("2026-09-29 03:00:00", ts)

    def test_arms_match_without_ts_counts_as_done(self):
        self._ab("2026-09-29 03:00:00", ["speedvaluebc", "speedvaluebcmeldp45"], ["speedvaluebc"])
        self._mark("ts= base=speedvaluebc cands=speedvaluebcmeldp45\n")
        done, ts, why = g.already_switched("yaku4", self.mk, self.ab)
        self.assertTrue(done, why)
        self.assertEqual("2026-09-29 03:00:00", ts)

    def test_other_window_is_not_done(self):
        self._ab("2026-09-26 08:00:00", ["speedvalue", "speedvaluebc"], ["speedvalue"])
        self._mark("ts=2026-09-29 03:00:00 base=speedvaluebc cands=speedvaluebcmeldp45\n")
        self.assertFalse(g.already_switched("yaku4", self.mk, self.ab)[0])

    def test_no_ab_mode_is_not_done(self):
        self._mark("ts=2026-09-29 03:00:00 base=speedvaluebc cands=speedvaluebcmeldp45\n")
        self.assertFalse(g.already_switched("yaku4", self.mk, self.ab)[0])

    def test_source_writes_marker_before_registering(self):
        src = io.open(os.path.join(ROOT, "var", "_bsegment.py"), encoding="utf-8").read()
        self.assertIn("switched_mark(a.label)", src)
        self.assertIn("already_switched(a.label)", src)
        # ★ 标记必须写在**注册看护之前**（否则注册失败时重试会重切）
        # ★ 注意：`_register_campaign_watches.ps1` 第一次出现是 dry-run 的**打印**
        #   ⇒ 必须取**最后一次**（=真的 run() 调用）才能比较顺序。
        self.assertLess(src.index("with io.open(switched_mark(a.label)"),
                        src.rindex("_register_campaign_watches.ps1"))


if __name__ == "__main__":
    unittest.main()
