# -*- coding: utf-8 -*-
"""`var/_ab_driver.py::abort_note` 的单测（R1472）。

为什么要钉：熔断分支会**删掉 `var/.ab_mode`**，而 watchdog / `_ensure_all.py` / `ab_ctl` 都
**只在 `.ab_mode` 在位时**才自愈 ⇒ 熔断之后**没有任何东西会再把驱动拉起来**：
本役房数永远冻在当前值、判词永远到不了 80/120 房 ⇒ **整条役次链静默停摆**。
（历史上熔断真的触发过 2 次：09-16 `speedc073w4`、09-20 `speedc151`，都靠人发现才续上。）

本次修复把「静默」变成「响亮 + 可照抄的恢复命令」。下面几条断言保证标记里**必须**含：
① 本役起始窗口（`--started`）② 原始臂集与顺序 ③ 一条可直接执行的 `ab_ctl` 恢复命令。
否则看护看到了也救不回来 —— 那和静默没区别。
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _ab_driver as D  # noqa: E402

ARMS = ["speedvalue", "speedvaluebc", "speedvaluebaotouv5"]
STARTED = "2026-09-25 20:52:39"


class TestAbortNote(unittest.TestCase):
    def _note(self, **kw):
        args = dict(arms=ARMS, started=STARTED, bundles=["speedvalue"],
                    bad_arm="speedvaluebc", gn=6, gmean=-412.5, gbase=8.3)
        args.update(kw)
        return D.abort_note(**args)

    def test_carries_window_arms_and_reason(self):
        t = self._note()
        self.assertIn(STARTED, t)
        self.assertIn("speedvaluebc", t)
        for a in ARMS:
            self.assertIn(a, t)
        self.assertIn("熔断", t)

    def test_resume_command_is_copyable(self):
        t = self._note()
        hit = [x for x in t.splitlines() if "ab_ctl.py start" in x and "speedvaluebc" in x]
        self.assertEqual(1, len(hit), t)
        self.assertIn("--bundles=speedvalue", hit[0])
        self.assertIn("--started=\"%s\"" % STARTED, hit[0])
        # 臂集与顺序必须原样可复制（基线与候选的相对顺序不能变）
        self.assertIn(",".join(ARMS), hit[0])

    def test_baseline_only_command_when_candidate_is_really_broken(self):
        t = self._note()
        hit = [x for x in t.splitlines() if "ab_ctl.py start speedvalue 1" in x]
        self.assertEqual(1, len(hit), t)

    def test_bundles_defaults_to_baseline(self):
        self.assertIn("--bundles=speedvalue", self._note(bundles=None))

    def test_missing_started_does_not_crash(self):
        t = self._note(started="")
        self.assertIn("(未知)", t)

    def test_marker_path_is_in_var(self):
        self.assertTrue(D.ABORTED.replace("\\", "/").endswith("var/.CAMPAIGN_ABORTED"), D.ABORTED)


if __name__ == "__main__":
    unittest.main()
