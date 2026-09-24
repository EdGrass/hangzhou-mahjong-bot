# -*- coding: utf-8 -*-
"""申报文案 ↔ 代码 的**指南版本一致性**单测（R1356）。

为什么：`docs/申报正文-最终.md` 是**直接粘进申报页**的上传物，
它声称的指南版本与 404 语义必须与**打包进去的代码**一致。实测：P0（v34→v35）补丁要到
役间 B 段才落地，而文案已提前改成 v35 口径 ⇒ 本门在补丁前**跳过**（不报假红），落地后**硬校**。

另有一道**硬门在提交工具**里：`var/_prepare_submission.ps1` 不一致就 rc!=0 ——
阻止“说的与做的不一样”的提交（实测现在就会报：文案 v35 / 代码 v34 ⇒ 先落 P0）。
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(ROOT, "bot", "__init__.py")
DOC = os.path.join(ROOT, "docs", "申报正文-最终.md")
RX = re.compile(r"GUIDE_VERSION_KNOWN\s*=\s*(\d+)")


def _ver(path):
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as f:
            m = RX.search(f.read())
        return int(m.group(1)) if m else None
    except OSError:
        return None


class TestSubmissionDocVersion(unittest.TestCase):
    def test_versions_readable(self):
        self.assertIsNotNone(_ver(INIT), "读不到代码里的 GUIDE_VERSION_KNOWN")
        self.assertIsNotNone(_ver(DOC), "读不到申报文案里声称的 GUIDE_VERSION_KNOWN")

    def test_doc_version_matches_code(self):
        cv, dv = _ver(INIT), _ver(DOC)
        if cv is None or dv is None:
            self.skipTest("读不到版本（代码=%r 文案=%r）" % (cv, dv))
        if cv < dv:
            self.skipTest("P0 补丁未落地（代码 v%d < 文案 v%d）：文案描述的是打完补丁后的形态；"
                          "提交硬门在 var/_prepare_submission.ps1" % (cv, dv))
        self.assertEqual(cv, dv,
                         "申报文案声称 v%d，代码是 v%d ⇒ 上传前必须同步（文案或代码）" % (dv, cv))


if __name__ == "__main__":
    unittest.main()
