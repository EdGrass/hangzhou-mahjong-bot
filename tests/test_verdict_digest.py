# -*- coding: utf-8 -*-
"""★ R1547：`var/_verdict_digest.py`（判词当天一屏摘要）的单测。

为什么：它把读卡要求的 6 条命令压成 1 条，判词当天只跑它。若它自己写错了顺序或漏了一步，
反而会把一个“以为全跑了”的假安全感带给判词人。所以钉：固定顺序、读数摘取、dry-run 零副作用。
"""
from __future__ import annotations
import contextlib
import importlib.util
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))


def _load():
    spec = importlib.util.spec_from_file_location("vdigest_t", os.path.join(ROOT, "var", "_verdict_digest.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["vdigest_t"] = m
    spec.loader.exec_module(m)
    return m


g = _load()

GATE2_SAMPLE = u"""端点                         基线        候选         差        z        判定
和牌率/房(主)               25.00     25.62     +0.62    +0.28 undecided
★ 判定：UNDECIDED（和牌率 z=+0.28、番 z=+0.58）⇒ 继续攒房
"""
HALF_B_SAMPLE = u"""speedvalue 我方          局   1280 | 胡/轮 25.00% | 分/轮   +0.02
speedvaluebc 我方        局   1280 | 胡/轮 25.62% | 分/轮   +0.64
★ 我方                    局   2560 | 胡/轮 25.31%
"""


class TestPickLines(unittest.TestCase):
    def test_extracts_verdict_line(self):
        out = g.pick_lines(GATE2_SAMPLE)
        self.assertTrue(any(x.startswith(u"★ 判定：") for x in out), out)

    def test_extra_matches_arm_rows(self):
        plain = g.pick_lines(HALF_B_SAMPLE)
        self.assertFalse(any(u"speedvaluebc" in x for x in plain),
                         u"不给 extra 时臂行不会被挑出（这正是当初两半那两段为空的原因）")
        witharm = g.pick_lines(HALF_B_SAMPLE, extra=["speedvaluebc"])
        self.assertTrue(any(u"speedvaluebc" in x for x in witharm), witharm)

    def test_limit_keeps_tail(self):
        text = u"\n".join(u"★ 判定：第%d" % i for i in range(30))
        out = g.pick_lines(text, limit=3)
        self.assertEqual(3, len(out))
        self.assertIn(u"第29", out[-1])


class TestCmdsFor(unittest.TestCase):
    def test_order_and_count(self):
        steps = g.cmds_for("T", "base", ["c1", "c2"], "none", 80, 32)
        names = [n for n, _ in steps]
        self.assertEqual(6, len(steps), names)
        self.assertEqual(["gate2/c1", "gate2/c2", "veto/c1", "veto/c2"], names[:4])
        self.assertTrue(names[4].startswith("half-A"))
        self.assertTrue(names[5].startswith("half-B"))

    def test_gate2_flags(self):
        (_, cmd), = [x for x in g.cmds_for("T", "base", ["c1"], "melds", 80, 32)
                     if x[0].startswith("gate2/")]
        for flag in ("--since", "--baseline", "--candidate", "--mechanism", "--min-rooms"):
            self.assertIn(flag, cmd, cmd)
        self.assertIn("T", cmd)
        self.assertIn("melds", cmd)

    def test_halves_go_through_lowprio(self):
        for name, cmd in g.cmds_for("T", "base", ["c1"], "none", 80, 32):
            if name.startswith("half-"):
                self.assertIn("_lowprio_run.py", " ".join(cmd), name)


class TestDryRun(unittest.TestCase):
    def test_dry_run_prints_and_says_so(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = g.main(["--since", "2026-09-25 20:52:39", "--baseline", "speedvalue",
                         "--candidates", "speedvaluebc,speedvaluebaotouv5", "--dry-run"])
        self.assertEqual(0, rc)
        t = buf.getvalue()
        self.assertIn("gate2/speedvaluebc", t)
        self.assertIn("half-B", t)
        self.assertIn(u"试跑", t)


if __name__ == "__main__":
    unittest.main()
