# -*- coding: utf-8 -*-
"""`var/_switch_final.marker_text` \u7684\u5355\u6d4b\uff1a10/7 \u5b89\u88c5\u51ed\u8bc1\u91cc\u5fc5\u987b\u5e26\u7740 **10/10 \u53ef\u76f4\u63a5\u6267\u884c\u7684\u6b63\u5f0f\u8d5b\u547d\u4ee4**\u3002

\u4e3a\u4ec0\u4e48\u8981\u9489\uff1a\u6b63\u5f0f\u8d5b\u5f53\u5929\u8981\u628a\u540c\u4e00\u4e2a\u81c2\u4f20\u7ed9 `_switch_to_official.ps1`\uff1b\u82e5\u51ed\u8bc1\u91cc\u53ea\u6709\u201c\u88c5\u4e86\u54ea\u4e2a\u81c2\u201d
\u800c\u6ca1\u6709\u547d\u4ee4\uff0c\u4e34\u573a\u53c8\u8981\u62fc\u53c2\u6570\uff08\u800c\u4e14\u5fc5\u987b\u786e\u4fdd\u7528\u7684\u5c31\u662f\u88c5\u597d\u7684\u90a3\u4e2a\u81c2\uff09\u3002
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _switch_final as SF  # noqa: E402


class TestMarkerText(unittest.TestCase):
    def test_contains_arm_and_commands(self):
        t = SF.marker_text("speedvaluebcvmeldp40", [1234])
        self.assertIn("arm=speedvaluebcvmeldp40", t)
        self.assertIn("keeper=[1234]", t)
        self.assertIn("_ready_1024.py --tid <TID> --token-file <TOK>", t)
        self.assertIn("-Strategy speedvaluebcvmeldp40", t)
        self.assertIn("_switch_to_official.ps1", t)

    def test_allow_not_ready_only_as_note(self):
        t = SF.marker_text("speedvalue", [1])
        cmd = [l for l in t.splitlines() if "_switch_to_official.ps1" in l][0]
        self.assertNotIn("-AllowNotReady", cmd)
        self.assertIn("-AllowNotReady", t)


if __name__ == "__main__":
    unittest.main()