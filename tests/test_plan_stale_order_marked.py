# -*- coding: utf-8 -*-
"""**计划“过期役序”标记门**（R1368）：单源真相文档里，**历史役序必须显式标注已被取代**。

为什么：`next-month-plan-20260923.md` 是**唯一权威**，而它会随证据不断追加章节。实测（2026-09-24）发现
**6 处**写过役序（§V.2 / §V.5 / §V.9 / §V.22 / §V.40 / §V.42），其中 §V.42 写的是“役 4 = V”，
但更晚的 §V.48 已把 V **并进役 3**（三臂役）、§V.49 定了“役 4 = 副露分支”——**照 §V.42 执行会重复跑 V（~20h）**。
所以给这 6 处补了统一标记，并用本门把它们钉住：**删标记 / 再写新的过期役序（不带标记）都会变红**。
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "docs", "iter", "reports", "next-month-plan-20260923.md")
# 已知的历史役序章节（正则匹配标题）
STALE_HEADS = [r"^### V\.2 ", r"^### V\.5 ", r"^### V\.9 ", r"^### V\.22 ", r"^### V\.40 ", r"^### V\.42 "]
MARK = "§V.48 / §V.49 取代"


class TestPlanStaleOrderMarked(unittest.TestCase):
    def _lines(self):
        self.assertTrue(os.path.exists(PLAN), "计划文档不存在")
        with io.open(PLAN, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_stale_sections_are_marked(self):
        L = self._lines()
        bad, seen = [], 0
        for pat in STALE_HEADS:
            rx = re.compile(pat)
            hit = [i for i, l in enumerate(L) if rx.match(l)]
            if not hit:
                bad.append("%s 标题找不到" % pat)
                continue
            seen += 1
            i = hit[0]
            if MARK not in "\n".join(L[i:i + 6]):
                bad.append("%s （第 %d 行）缺少“%s”标记" % (pat, i + 1, MARK))
        self.assertGreaterEqual(seen, 5, "应至少找到 5 个历史役序章节（否则本门是空跑）")
        self.assertEqual([], bad, "以下历史役序章节缺少“已被取代”标记 ⇒ 可能被误当当前役序执行：%s" % bad)

    def test_current_order_is_documented(self):
        """现行役序（§V.48/§V.49）必须存在（否则标记指向空处）。"""
        L = self._lines()
        has48 = any(l.startswith("### V.48 ") for l in L)
        has49 = any(l.startswith("### V.49 ") for l in L)
        self.assertTrue(has48 and has49, "当前役序章节 V.48/V.49 应存在")


if __name__ == "__main__":
    unittest.main()
