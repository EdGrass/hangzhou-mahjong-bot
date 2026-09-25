# -*- coding: utf-8 -*-
"""\u2605 R1511\uff1a`_switch_campaign.py` \u7684\u63d0\u793a\u4e0d\u5f97\u4e0e\u7ea2\u7ebf\u300c\u4e0d\u52a8\u53f0\u8d26\u300d\u51b2\u7a81\u3002

\u4e3a\u4ec0\u4e48\u8981\u9489\uff1a\u8be5\u811a\u672c\u4f1a\u5728**\u6bcf\u4e2a\u5f79\u5207\u6362**\u65f6\u6253\u5370\u53f0\u8d26\u91cc\u7684\u5386\u53f2 `running` \u6b8b\u7559\u884c\u3002
\u539f\u53e5\u662f\u201c\u4e0d\u5f71\u54cd\u5207\u6362\uff0c**\u4f46\u5efa\u8bae\u6e05\u7406**\u201d\u2014\u2014 \u800c\u672c\u9879\u76ee\u7ea2\u7ebf\u662f**\u4e0d\u52a8\u53f0\u8d26**\uff08\u53f0\u8d26\u53ea\u8ffd\u52a0\uff09\uff0c
\u7167\u7740\u201c\u5efa\u8bae\u201d\u53bb\u5220\u884c = \u8fdd\u89c4\u4e14\u7834\u574f\u8bc1\u636e\u94fe\u3002\u672c\u6d4b\u8bd5\u628a\u63aa\u8f9e\u9489\u4f4f\u3002
"""
from __future__ import annotations
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "var", "_switch_campaign.py")


@unittest.skipUnless(os.path.exists(SRC), "var/ \u4e0d\u5728\u4ed3\u5e93\u91cc\uff08gitignore\uff09")
class TestSwitchCampaignRedline(unittest.TestCase):
    def test_stale_ledger_message_defers_to_redline(self):
        s = io.open(SRC, encoding="utf-8").read()
        self.assertIn("\u53f0\u8d26\u6b8b\u7559", s)
        self.assertNotIn("\u4f46\u5efa\u8bae\u6e05\u7406", s, "\u4e0d\u5f97\u5efa\u8bae\u6e05\u7406\u53f0\u8d26\uff08\u7ea2\u7ebf\uff1a\u4e0d\u52a8\u53f0\u8d26\uff09")
        self.assertIn("\u4e0d\u8981\u624b\u6539", s)


if __name__ == "__main__":
    unittest.main()