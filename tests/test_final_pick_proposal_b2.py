# -*- coding: utf-8 -*-
"""★ R1535：10/5 选臂提案必须能让人看到 **B2 备选臂**的读数。

为什么：预登记（campaign3 §4 B2 / campaign7 §4 B2）要求把「机制成立、主端点未证实」的臂
**保留为正式赛备选**、与 §V.66 口径**并行比较**；`_adopt_pair` 也确实把它们落进
`var/.B2_CANDIDATES`。但**生成"比较材料"的脚本（`_final_pick_proposal.py`）原本不读它**
⇒ 10/5（唯一的人工决策材料）里看不到这些臂 ⇒ 预登记要求的"并行比较"落空，
`.B2_CANDIDATES` 就变成又一个"写了没人读"。

本文件钉两件事：① 解析器认得 `_adopt_pair` 的真实文件格式；② main() 真的会把这一段接进去。
"""
from __future__ import annotations
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _final_pick_proposal as M  # noqa: E402

# 与 `_adopt_pair` 写出来的格式逐字对齐（含窗口）
B2_TEXT = u"""2026-09-28 06:31:00 役三层 B2 备选臂（窗口 since=2026-09-25 20:52:39；预登记：机制成立、主端点未证实）
  speedvaluebc —— 机制成立、主端点未证实（判词：UNDECIDED（和牌率 z=+1.24、番 z=+1.41）⇒ 继续攒房）
注：他们**没有**通过预登记判词 ⇒ 按 §V.161 规则 1 **不进自动候选池**；
但预登记要求把它们保留为正式赛备选，与 §V.66/§V.29 口径**并行比较**（由人判）。
"""


class TestParseB2(unittest.TestCase):
    def test_reads_window_and_arms(self):
        win, arms = M.parse_b2(B2_TEXT)
        self.assertEqual("2026-09-25 20:52:39", win)
        self.assertEqual(["speedvaluebc"], arms)

    def test_ignores_title_note_and_indented_prose(self):
        txt = B2_TEXT + u"  这是一行两空格缩进但没有破折号的说明\n  注：别被当成臂\n"
        _, arms = M.parse_b2(txt)
        self.assertEqual(["speedvaluebc"], arms)

    def test_missing_window_is_reported_as_empty(self):
        win, arms = M.parse_b2(u"x B2 备选臂\n  speedvaluebaotouv5 —— 机制成立\n")
        self.assertEqual("", win)
        self.assertEqual(["speedvaluebaotouv5"], arms)

    def test_empty_text(self):
        self.assertEqual(("", []), M.parse_b2(""))
        self.assertEqual(("", []), M.parse_b2(None))


class TestB2Section(unittest.TestCase):
    def _stub(self, stdout=u"STUB-READOUT\n"):
        return mock.Mock(stdout=stdout, returncode=0, stderr=u"")

    def test_section_keeps_the_discipline_line_and_runs_own_window(self):
        with mock.patch.object(M.subprocess, "run", return_value=self._stub()) as run:
            out = M.b2_section(B2_TEXT)
        self.assertIn(u"不进自动池", out)
        self.assertIn(u"§V.161 规则 4", out)
        self.assertIn(u"不可混读", out)
        self.assertIn(u"STUB-READOUT", out)
        argv = run.call_args[0][0]                 # 第一次调用 = _pick_arm.py
        self.assertIn("_pick_arm.py", " ".join(argv))
        self.assertIn("2026-09-25 20:52:39", argv)  # ★ 必须用它**自己那一役**的窗口

    def test_section_states_the_r1557_discipline(self):
        """★ R1557：这段必须写死“**未判正的臂不入最终臂候选池**”。

        为什么：§V.161 A.1（已写死“不能事后挑”）+ campaign8 §4-4 都禁止部署未判正臂；
        而 §V.247 的“全部臂”只是**列出/比较**的范围 —— 不能被读成“可以据此部署”。
        """
        out = M.b2_section(B2_TEXT)
        # 正文里“（含 B2）”夹在中间 ⇒ 查关键子串（不拟合整句）
        self.assertIn(u"不入最终臂候选池", out)
        self.assertIn(u"§V.161 A.1", out)
        self.assertIn(u"不得据此写", out)
        self.assertIn(u"R1557", out)

    def test_no_window_tells_the_human_what_to_run(self):
        out = M.b2_section(u"x B2 备选臂\n  speedvaluebc —— 机制成立\n")
        self.assertIn(u"_pick_arm.py --since", out)


class TestWiring(unittest.TestCase):
    """端到端：B2 标记在场时，main() 必须把这一段接进提案正文。"""

    def test_main_appends_b2_section(self):
        d = tempfile.TemporaryDirectory()
        try:
            b2 = os.path.join(d.name, ".B2_CANDIDATES")
            with io.open(b2, "w", encoding="utf-8") as f:
                f.write(B2_TEXT)
            stub = mock.Mock(stdout=u"STUB-READOUT\n", returncode=0, stderr=u"")
            out = io.StringIO()
            with mock.patch.object(M, "B2", b2), \
                 mock.patch.object(M, "AB", os.path.join(d.name, "no_such_ab_mode")), \
                 mock.patch.object(M.subprocess, "run", return_value=stub), \
                 mock.patch.object(sys, "argv", ["x", "--dry-run"]), \
                 mock.patch("sys.stdout", out):
                rc = M.main()
            t = out.getvalue()
            self.assertEqual(0, rc)
            self.assertIn(u"B2 备选臂", t)
            self.assertIn(u"STUB-READOUT", t)
        finally:
            d.cleanup()

    def test_main_has_no_b2_section_when_marker_absent(self):
        d = tempfile.TemporaryDirectory()
        try:
            stub = mock.Mock(stdout=u"STUB-READOUT\n", returncode=0, stderr=u"")
            out = io.StringIO()
            with mock.patch.object(M, "B2", os.path.join(d.name, "no_b2")), \
                 mock.patch.object(M, "AB", os.path.join(d.name, "no_such_ab_mode")), \
                 mock.patch.object(M.subprocess, "run", return_value=stub), \
                 mock.patch.object(sys, "argv", ["x", "--dry-run"]), \
                 mock.patch("sys.stdout", out):
                M.main()
            self.assertNotIn(u"B2 备选臂", out.getvalue())
        finally:
            d.cleanup()

    def test_source_reads_the_marker(self):
        s = io.open(os.path.join(ROOT, "var", "_final_pick_proposal.py"), encoding="utf-8").read()
        self.assertIn(u".B2_CANDIDATES", s)
        self.assertIn(u"read_text(B2)", s)


if __name__ == "__main__":
    unittest.main()
