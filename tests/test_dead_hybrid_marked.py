# -*- coding: utf-8 -*-
"""**已否决功能**主题门（R1382）：`hybrid /state` 的每一处提及都必须带"已否决"标记。

背景（真实隐患）：`hybrid /state` 在**更早的**两份文档里被写成"役 3 起役时要应用的改进"
（计划 §A 同期附加、§U-6 排期表、runbook §7.6），但**更晚**的结论已把它否决并关闭
（计划 L466/L484、runbook §9.1）：实测 p50 **744→3768ms**（登记竞态）⇒ 会**毁掉决策延迟**。

⇒ 若有人（或未来的我）在**役 3 的切换窗口**照着旧行执行，就会把一个"已实测有害"的补丁接上。
本门把"**提到 hybrid 就必须紧邻一行写着已否决**"钉死（含 runbook —— 它是操作员手册）。
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = [
    "docs/iter/reports/next-month-plan-20260923.md",
    "docs/iter/reports/competition-runbook-20260923.md",
]
# ★ 扩成“主题词”：只要提到 hybrid 就必须带排除性标记（否则实测下面那种
#   “hybrid `/state`”的纯文字提法会漏网）。
KEYS = ("hybrid",)
MARKERS = ("已否决", "不得", "已关闭", "不要再投入", "天花板")


class TestDeadHybridMarked(unittest.TestCase):
    def _scan(self, docs):
        out = []
        for d in docs:
            p = os.path.join(ROOT, d.replace("/", os.sep))
            if not os.path.exists(p):
                continue
            with io.open(p, encoding="utf-8", errors="replace") as fh:
                L = fh.read().splitlines()
            for i, l in enumerate(L, 1):
                if any(k.lower() in l.lower() for k in KEYS):
                    win = "\n".join(L[max(0, i - 3):i + 2])
                    out.append((d, i, any(m in win for m in MARKERS), l.strip()[:90]))
        return out

    def test_gate_sees_mentions(self):
        hits = self._scan(DOCS)
        self.assertGreaterEqual(len(hits), 3,
                                "应至少看到 3 处 hybrid 提及（否则本门是空跑）；实际 %d" % len(hits))

    def test_every_mention_is_marked_dead(self):
        bad = [(d, i, l) for d, i, ok, l in self._scan(DOCS) if not ok]
        self.assertEqual([], bad,
                         "以下提及 hybrid 的行**缺“已否决/不得”标记** ⇒ 可能被误当“要应用的改进”执行：%s" % bad)


if __name__ == "__main__":
    unittest.main()
