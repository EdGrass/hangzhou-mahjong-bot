# -*- coding: utf-8 -*-
"""★ R1542：**入口文档防漂移门** —— HANDOFF 里的“最新 R”与“§V 范围”必须与日志/计划一致。

为什么：HANDOFF 是接手时第一个读的文件，而这两个数字是**手工**更新的
—— 本会话我已**两次**漏改（R1541 那轮没改“最新 R”那行）。门一扮，以后不会再漂。
"""
from __future__ import annotations
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDOFF = os.path.join(ROOT, "docs", "HANDOFF.md")
JOURNAL = os.path.join(ROOT, "docs", "iter", "journal.md")
PLAN = os.path.join(ROOT, "docs", "iter", "reports", "next-month-plan-20260923.md")


def read(p):
    with io.open(p, encoding="utf-8-sig", errors="replace") as fh:   # ★ 句柄必关
        return fh.read()


@unittest.skipUnless(all(os.path.exists(p) for p in (HANDOFF, JOURNAL, PLAN)), "缺入口文档")
class TestHandoffFreshness(unittest.TestCase):
    def test_latest_R_matches_journal(self):
        h = read(HANDOFF)
        m = re.search(r"最新\s*\*\*R(\d+)\*\*", h)
        self.assertIsNotNone(m, "HANDOFF 里应有“最新 **R<n>**”")
        r_doc = int(m.group(1))
        r_log = max(int(x) for x in re.findall(r"(?m)^- \[R(\d+) \|", read(JOURNAL)))
        self.assertEqual(r_log, r_doc, "入口文档写 R%d，日志最新是 R%d" % (r_doc, r_log))

    def test_latest_section_matches_plan(self):
        h = read(HANDOFF)
        m = re.search(r"§A–§V\.(\d+)", h)
        self.assertIsNotNone(m, "HANDOFF 里应有“§A–§V.<n>”")
        n_doc = int(m.group(1))
        n_plan = max(int(x) for x in re.findall(r"(?m)^### §?V\.(\d+)", read(PLAN)))
        self.assertEqual(n_plan, n_doc, "入口文档写 §V.%d，计划最新是 §V.%d" % (n_doc, n_plan))


if __name__ == "__main__":
    unittest.main()
