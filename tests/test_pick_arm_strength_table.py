# -*- coding: utf-8 -*-
"""\u2605 R1512\uff1a`_pick_arm.py` \u7684**\u5bf9\u624b\u5f3a\u5ea6\u8bfb\u6570**\u5fc5\u987b\u5728\uff0c\u4e14\u4e0d\u5f97\u6539\u53d8 \u00a7V.66 \u7684\u6392\u5e8f/\u9608\u503c\u3002

\u4e3a\u4ec0\u4e48\u8981\u9489\uff1a10/5 \u5b9a\u81c2\u9760\u7684\u5c31\u662f\u8fd9\u5f20\u8868\u3002\u4e09\u81c2\u662f round-robin \u5f00\u7684\uff08\u623f\u6570\u5929\u7136\u5bf9\u79f0\uff09\uff0c
\u4f46**\u684c\u5f3a**\u4ecd\u53ef\u80fd\u4e0d\u5bf9\u79f0\uff08\u5b9e\u6d4b\uff1a\u5f793 \u7a97\u53e3\u5404\u81c2\u684c\u5f3a -6.7 / -9.9 / +33.6\uff09\u3002
\u628a\u5b83\u653e\u8fdb\u540c\u4e00\u5f20\u8bfb\u6570\u91cc\uff0c\u80fd\u907f\u514d\u201c\u628a\u684c\u5dee\u5f53\u7b56\u7565\u5dee\u201d\uff1b\u4f46**\u53ea\u80fd\u662f\u8bfb\u6570**\uff0c\u6392\u5e8f\u4ecd\u5fc5\u987b\u6309\u5f3a\u624b\u623f\u5206/\u623f\u3002
"""
from __future__ import annotations
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "var", "_pick_arm.py")


@unittest.skipUnless(os.path.exists(SRC), "var/ \u4e0d\u5728\u4ed3\u5e93\u91cc\uff08gitignore\uff09")
class TestPickArmStrengthTable(unittest.TestCase):
    def test_source_has_strength_readout_and_keeps_ordering(self):
        s = io.open(SRC, encoding="utf-8").read()
        self.assertIn("\u5bf9\u624b\u5f3a\u5ea6\uff08\u56e0\u679c\u53e3\u5f84", s)
        self.assertIn("\u684c\u5f3a\u8c03\u6574\u540e\u51c0\u80dc", s)
        self.assertIn("\u53ea\u4f5c\u8bfb\u6570", s)
        # \u6392\u5e8f\u5fc5\u987b\u4ecd\u7136\u662f \u00a7V.66 \u7684\u4e3b\u5e8f\u5217\uff08\u5f3a\u624b\u623f\u5206/\u623f\uff09\u2014\u2014\u684c\u5f3a\u53ea\u80fd\u5f71\u54cd\u8bfb\u6570\uff0c\u4e0d\u80fd\u5f71\u54cd\u6b21\u5e8f
        self.assertIn('table.sort(key=lambda r: (-r["mean_strong"]', s)

    def test_runs_and_prints_readout(self):
        if not os.path.exists(os.path.join(ROOT, "var", "auto_ranking.jsonl")):
            self.skipTest("\u7f3a var/auto_ranking.jsonl\uff08clone\uff09")
        p = subprocess.run([sys.executable, "-X", "utf8", SRC, "--since", "2026-09-25 20:52:39",
                            "--min-rooms", "3"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, p.returncode, p.stderr[-400:])
        self.assertIn("\u5bf9\u624b\u5f3a\u5ea6", p.stdout)
        self.assertIn("\u03b2=", p.stdout)


    def test_veto_precheck_is_inline(self):
        """★ R1518：役 5 的两层否决必须**出现在选臂表的输出里**（不能只写在读卡/命令里）。"""
        src = io.open(SRC, encoding="utf-8").read()
        self.assertIn("否决预检", src)
        self.assertIn("_strong_veto.py", src)
        if not os.path.exists(os.path.join(ROOT, "var", "auto_ranking.jsonl")):
            self.skipTest("缺 var/auto_ranking.jsonl（clone）")
        p = subprocess.run([sys.executable, "-X", "utf8", SRC, "--since", "2026-09-25 20:52:39",
                            "--min-rooms", "3"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        self.assertEqual(0, p.returncode, p.stderr[-300:])
        self.assertIn("否决预检", p.stdout)
        self.assertIn("rc=", p.stdout)


if __name__ == "__main__":
    unittest.main()