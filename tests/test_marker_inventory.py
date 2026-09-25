# -*- coding: utf-8 -*-
"""★ R1492：**运行期标记总账**的回归门。

为什么要钉：这一周同类“写了但没人执行 / 没人读”抓出 **12 个**（journal R1460–R1491）。
单个修完不算完，要让**新标记不能再偷偷流进来**：凡在下面这批“红线脚本”里出现新的 `".X"` 字面量，
**必须已经在 `docs/iter/reports/heartbeat-marker-inventory.md` 里有一行**（写清谁写/谁读/看护第几步报）。
否则就是在制造第 13 个“没人执行”。
"""
from __future__ import annotations
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "iter", "reports", "heartbeat-marker-inventory.md")

# 这批是“写状态/标记”的红线脚本：新标记必须在总账里
CRITICAL = [
    "_ab_driver.py", "_mech_watch.py", "_adopt_pair.py", "_next_yaku_notice.py",
    "_schedule_guard.py", "_final_arm_confirm.py", "_final_ready_check.py",
    "_final_event_switch.py", "_final_event_ready.py", "_submit_final.py",
    "_portal_watch.py", "_ensure_all.py", "_switch_final.py",
]
PAT = re.compile(r'"\.([A-Za-z_][A-Za-z0-9_]{2,})"')


class TestMarkerInventory(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.exists(DOC), DOC)

    def test_every_marker_in_critical_scripts_is_documented(self):
        doc = io.open(DOC, encoding="utf-8").read()
        missing = []
        for s in CRITICAL:
            p = os.path.join(ROOT, "var", s)
            if not os.path.exists(p):
                continue
            txt = io.open(p, encoding="utf-8", errors="replace").read()
            for name in sorted(set(PAT.findall(txt))):
                if ("." + name) not in doc:
                    missing.append("%s -> .%s" % (s, name))
        self.assertEqual([], missing,
                         u"\u8fd9\u4e9b\u6807\u8bb0\u4e0d\u5728\u603b\u8d26\u91cc\uff08\u65b0\u6807\u8bb0\u5fc5\u987b\u540c\u65f6\u7ed9\u51fa\u201c\u8c01\u8bfb\u201d\u6216\u201c\u770b\u62a4\u7b2c\u51e0\u6b65\u62a5\u201d\uff09")

    def test_doc_lists_the_heartbeat_steps(self):
        doc = io.open(DOC, encoding="utf-8").read()
        for step in ("**0**", "**0b**", "**0c**", "**0d**", "**0e**", "**0f**", "**0g**"):
            self.assertIn(step, doc, step)


if __name__ == "__main__":
    unittest.main()
