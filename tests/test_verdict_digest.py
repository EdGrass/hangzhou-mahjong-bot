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
import tempfile
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


class TestReportWriting(unittest.TestCase):
    """★ R1550：真跑时报告必须**写出来**，且文件名带**时间戳**（同一窗口跑多次不互相覆盖）。

    为什么：此前只有纯函数单测，“报告写盘”这条路径没人跑过；而它是判词当天的**证据文件**。
    """

    def test_main_writes_timestamped_report(self):
        import tempfile, re as _re
        with tempfile.TemporaryDirectory() as d:
            class _P(object):
                stdout = "x\n"
                stderr = ""
                returncode = 0
            old_dir, old_run = g.OUT_DIR, g.subprocess.run
            g.OUT_DIR = d
            g.subprocess.run = lambda *a, **k: _P()
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = g.main(["--since", "2026-09-25 20:52:39", "--baseline", "speedvalue",
                                 "--candidates", "speedvaluebc,speedvaluebaotouv5", "--min-rooms", "10"])
            finally:
                g.OUT_DIR, g.subprocess.run = old_dir, old_run
            self.assertEqual(0, rc)
            files = os.listdir(d)
            self.assertEqual(1, len(files), files)
            self.assertRegex(files[0], r"^_verdict_digest_\d{14}_\d{8}_\d{6}\.txt$")
            with io.open(os.path.join(d, files[0]), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("机制端点", body)
            # ★ 注意：报告里记的是**完整命令行**（`$ -X utf8 ..._gate2.py ...`），
            #   `gate2/臂` 这个简名只在**屏幕**摘要里 ⇒ 别拿屏幕文本去断报告。
            self.assertIn("_gate2.py", body)
            self.assertIn("speedvaluebc", body)


class TestMechSection(unittest.TestCase):
    """★ R1548：机制端点（读卡 §0b/§0c）必须一并汇总。

    为什么：役3 的 V 机制**不在** `_gate2`（`--mechanism none`）里，而在 `_mech_watch` 写的那几个文件里；
    摘要不汇总它们，判词人就只看到一半证据。
    """

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)

    def _w(self, name, text):
        with io.open(os.path.join(self.d.name, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_markers_readings_and_log(self):
        self._w(".mech_warn", u"2026-09-26 07:00 speedvaluebc 足迹脱离预期\n")
        self._w(".v_mech_unknown", u"2026-09-26 06:36 V 轴机制读数缺失\n")
        self._w("_v_mech_readings.jsonl",
                u'{"arm": "speedvaluebaotouv5", "ok": true, "why": "旧"}\n'
                u'{"arm": "speedvaluebaotouv5", "ok": null, "why": "拖动"}\n'
                u'{"arm": "speedvaluebc", "ok": false, "why": "不达标"}\n')
        self._w("_mech_watch.log", u"line1\nline2\nline3\n")
        got = dict(g.mech_section(self.d.name, n_log=2))
        self.assertIn(u"足迹脱离", got[".mech_warn"])
        self.assertIn(u"V 轴", got[".v_mech_unknown"])
        self.assertEqual(u"（不存在）", got[".ADOPT_V_MECH_STALL"])
        # ★ 最新一条**非 None**的读数胜出（与 _adopt_pair.v_mech_verdict 同语义：抗瞬时抖动）
        self.assertTrue(got[u"V读数/speedvaluebaotouv5"].startswith("ok=True"),
                        got[u"V读数/speedvaluebaotouv5"])
        self.assertIn("ok=False", got[u"V读数/speedvaluebc"])
        self.assertNotIn("line1", got[u"_mech_watch.log 末2行"])
        self.assertIn("line3", got[u"_mech_watch.log 末2行"])

    def test_empty_dir(self):
        got = dict(g.mech_section(self.d.name))
        for name in g.MARKERS:
            self.assertEqual(u"（不存在）", got[name])
        self.assertIn(u"V读数", got)


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
