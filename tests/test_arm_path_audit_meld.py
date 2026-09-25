# -*- coding: utf-8 -*-
"""\u2605 R1514\uff1a`_arm_path_audit.py` \u4e0d\u5f97\u628a\u300c\u526f\u9732\u5c42\u81c2\u5728 draw \u5c42 0 \u5206\u6b67\u300d\u8bef\u62a5\u6210\u7ea2\u65d7\u3002

\u4e3a\u4ec0\u4e48\u8981\u9489\uff1a\u9884\u767b\u8bb0\u7684\u201c\u8d77\u5f79\u547d\u4ee4\u201d\u7b2c 1 \u6761\u5c31\u662f draw \u5c42\u5ba1\u8ba1\uff08`--arms <C> --baseline <B> --files 25 --limit 600`\uff09\uff1b
\u800c\u526f\u9732\u5c42\u81c2\u53ea\u5728**\u7d22\u53d6\u5c42**\u52a8\u4f5c \u21d2 draw \u5c42\u672c\u5c31\u5e94\u8be5 0 \u5206\u6b67\u3002\u539f\u5224\u636e\u5374\u62a5\u201c\u274c \u6709\u6a21\u578b\u5374 0 \u5206\u6b67\uff08\u7591\u4f3c\u9759\u9ed8\u515c\u5e95\uff09\u201d\uff08rc=2\uff09
\u21d2 \u6709\u4eba\u7167\u547d\u4ee4\u8dd1\u5c31\u53ef\u80fd**\u62d2\u7edd\u8d77\u5f79**\u3002\u73b0\u5728\uff1a\u53ea\u7ed9\u4fe1\u606f\u63d0\u793a\uff0crc=0\u3002
"""
from __future__ import annotations
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "var", "_arm_path_audit.py")


@unittest.skipUnless(os.path.exists(SRC), "var/ \u4e0d\u5728\u4ed3\u5e93\u91cc\uff08gitignore\uff09")
class TestMeldLayerNotFlagged(unittest.TestCase):
    def test_source_has_carve_out(self):
        s = io.open(SRC, encoding="utf-8").read()
        self.assertIn("\u526f\u9732\u5c42\u81c2\uff1adraw \u5c42 0 \u5206\u6b67\u5c5e\u9884\u671f", s)
        self.assertIn('_meld_layer = "meld" in name.lower()', s)
        self.assertIn("--phase window \u590d\u67e5\u7d22\u53d6\u5c42", s)

    def test_draw_phase_on_meld_arm_is_green_with_note(self):
        if not os.path.exists(os.path.join(ROOT, "var", "replays")):
            self.skipTest("\u65e0 var/replays\uff08clone\uff09")
        p = subprocess.run([sys.executable, "-X", "utf8", SRC, "--arms", "speedvaluemeldp45",
                            "--baseline", "speedvalue", "--files", "25", "--limit", "600"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        self.assertEqual(0, p.returncode, p.stdout[-500:] + p.stderr[-300:])
        self.assertIn("\u526f\u9732\u5c42\u81c2\uff1adraw \u5c42 0 \u5206\u6b67\u5c5e\u9884\u671f", p.stdout)


if __name__ == "__main__":
    unittest.main()