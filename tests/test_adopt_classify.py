# -*- coding: utf-8 -*-
"""`var/_adopt_when_ready.classify` \u7684\u5355\u6d4b\uff08\u7eaf\u51fd\u6570\uff0c\u65e0\u7f51\u7edc/\u65e0\u8fdb\u7a0b\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u8fd9\u4e2a\u5206\u7c7b\u51b3\u5b9a\u201c\u4eca\u591c\u5230\u5e95\u8fdb\u4e0d\u8fdb\u5f79 3\u201d\u3002\u82e5\u5b83\u628a UNDECIDED-\u672a\u8fbe\u76d2\u8bef\u5224\u6210 proceed\uff0c
\u4f1a\u5728\u623f\u6570\u4e0d\u8db3\u65f6\u63d0\u524d\u5207\u5f79\uff08\u767d\u4e22\u4e00\u5f79\uff09\uff1b\u82e5\u628a REFUSE/REJECT \u8bef\u5224\u6210 wait\uff0c\u53c8\u4f1a\u8ba9\u5f79 3 \u9759\u9ed8\u505c\u6446\u5230\u5929\u4eae\u3002
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _adopt_when_ready as A  # noqa: E402

M = "\u2605 \u5224\u5b9a\uff1a"


class TestAdoptClassify(unittest.TestCase):
    def test_adopt(self):
        self.assertEqual("proceed", A.classify(M + "ADOPT speedvalue\uff08\u548c\u724c\u7387 z=+1.8\u3001\u756a z=+1.6\uff09")[0])

    def test_reject_proceeds(self):
        self.assertEqual("proceed", A.classify(M + "REJECT speedvalue\uff08\u548c\u724c\u7387 z=-2.1\uff09")[0])

    def test_refuse_proceeds(self):
        self.assertEqual("proceed", A.classify(M + "REFUSE / CONTINUE \u2014\u2014 \u7b2c\u4e00\u7387\u62a4\u680f\u672a\u8fc7")[0])

    def test_undecided_box_proceeds(self):
        txt = "\u5df2\u8fbe\u5f79\u76d2\uff08>= 120 \u623f/\u81c2\uff09\n" + M + "UNDECIDED\uff08\u548c\u724c\u7387 z=+1.27\uff09"
        self.assertEqual("proceed", A.classify(txt)[0])

    def test_undecided_prebox_waits(self):
        self.assertEqual("wait", A.classify(M + "UNDECIDED\uff08\u548c\u724c\u7387 z=+0.9\uff09")[0])

    def test_empty_and_garbage_wait(self):
        self.assertEqual("wait", A.classify("")[0])
        self.assertEqual("wait", A.classify("\u4e00\u4e9b\u65e0\u5173\u6587\u5b57")[0])

    def test_last_line_wins(self):
        txt = M + "UNDECIDED\uff08z=+0.9\uff09\n" + M + "ADOPT speedvalue"
        self.assertEqual("proceed", A.classify(txt)[0])



class TestVerdictTag(unittest.TestCase):
    """判词标签 —— 日志不能一律写 "ADOPT"（classify 对所有终态都 proceed，本机实测被带偏过）。"""

    def test_tags(self):
        self.assertEqual("ADOPT", A.verdict_tag(M + "ADOPT speedvalue（和牌率 z=+1.8）"))
        self.assertEqual("REFUSE", A.verdict_tag(M + "REFUSE / CONTINUE —— 第一率护栏未过"))
        self.assertEqual("REJECT", A.verdict_tag(M + "REJECT speedvalue（和牌率 z=-2.1）"))
        self.assertEqual("UNDECIDED", A.verdict_tag(M + "UNDECIDED（和牌率 z=+0.9）⇒ 继续攒房"))

    def test_last_line_wins_and_empty(self):
        t = M + "REFUSE 旧\n" + M + "ADOPT speedvaluebc\n"
        self.assertEqual("ADOPT", A.verdict_tag(t))
        self.assertEqual("无判词", A.verdict_tag(""))
        self.assertEqual("无判词", A.verdict_tag("一些无关文字"))


if __name__ == "__main__":
    unittest.main()