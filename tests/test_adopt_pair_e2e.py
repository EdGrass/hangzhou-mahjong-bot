# -*- coding: utf-8 -*-
"""`var/_adopt_pair.py` 的**端到端接线测试**（R1496）。

为什么还要一层：现有单测只盖**纯函数**（`pick_row`/`classify_candidate`/`is_b2`/`v_rule_conflict`/`mech_state`）。
而役 3→役 4 是一次**串起来的裁决**（读两份判词 → 新增三道闸 → 四格 → 打印起下一役命令），
**`main()` 里的接线错一处，纯函数测试是看不见的**。本文件用**假 label + 临时判词文件**把四格跑一遍（`--dry-run`，
不碰进程、不启役），并验证新增的机制闸**真的会改变四格行**。

红线：只写**假 label**的临时文件（tearDown 删）；`run_veto` 输出被打桩（单测不该跑真的强手房计算）；
`B2_OUT` / `CONFLICT_OUT` 改指临时路径，**不碰真实标记**。
"""
from __future__ import annotations
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _adopt_pair as AP  # noqa: E402

LABEL = u"\u81ea\u6d4b_w9"
ARM_A, ARM_B = "speedvaluebc", "speedvaluebaotouv5"
ADOPT_A = u"ADOPT speedvaluebc\uff08\u548c\u724c\u7387 z=+1.80\u3001\u756a z=+1.60\u3001\u62a4\u680f\u901a\u8fc7\uff09"
ADOPT_B = u"ADOPT speedvaluebaotouv5\uff08\u548c\u724c\u7387 z=+1.55\u3001\u756a z=+1.70\u3001\u62a4\u680f\u901a\u8fc7\uff09"
REJECT_A = u"REJECT speedvaluebc\uff08\u548c\u724c\u7387 z=-2.0\u3001\u756a z=-1.8\uff09"
REJECT_B = u"REJECT speedvaluebaotouv5\uff08\u548c\u724c\u7387 z=-1.9\u3001\u756a z=-1.7\uff09"


def _w(p, text):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


class TestAdoptPairEndToEnd(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self._old = (AP.B2_OUT, AP.CONFLICT_OUT)
        AP.B2_OUT = os.path.join(self.d.name, ".B2_CANDIDATES")
        AP.CONFLICT_OUT = os.path.join(self.d.name, ".VERDICT_RULE_CONFLICT")
        self._paths = []
        for suf in ("bc", "v"):
            for pre in (".verdict_done_", "_verdict_"):
                p = os.path.join(ROOT, "var", pre + LABEL + suf + (".txt" if pre == "_verdict_" else ""))
                self._paths.append(p)

    def tearDown(self):
        AP.B2_OUT, AP.CONFLICT_OUT = self._old
        for p in self._paths:
            if os.path.exists(p):
                os.remove(p)
        self.d.cleanup()

    def _fixture(self, line_a, line_b, mech_warn=None):
        for suf, line in (("bc", line_a), ("v", line_b)):
            _w(os.path.join(ROOT, "var", ".verdict_done_" + LABEL + suf), "x")
            _w(os.path.join(ROOT, "var", "_verdict_" + LABEL + suf + ".txt"),
                u"★ 判定：" + line + "\n")
        if mech_warn is not None:
            _w(AP.MECH_WARN, mech_warn) if False else None

    def _run(self, line_a, line_b, warn_text=None, warn_arm=None):
        self._fixture(line_a, line_b)
        out = io.StringIO()
        patches = [mock.patch.object(AP, "run_veto", return_value=(0, "stub")),
                   mock.patch.object(AP, "mech_state", return_value=("ok", "stub"))]
        if warn_arm is not None:
            patches[-1] = mock.patch.object(AP, "mech_state",
                                            side_effect=lambda arm, since, path=None:
                                            (("fail", "\u8db3\u8ff9\u544a\u8b66") if arm == warn_arm else ("ok", "stub")))
        for p in patches:
            p.start()
        try:
            with mock.patch.object(sys, "argv",
                                   ["x", "--label", LABEL, "--baseline", "speedvalue",
                                    "--dry-run"]), mock.patch("sys.stdout", out):
                AP.main()
        finally:
            for p in patches:
                p.stop()
        return out.getvalue()

    def test_bc_adopt_takes_row_a(self):
        t = self._run(ADOPT_A, ADOPT_B)
        self.assertIn("--baseline speedvaluebc", t)
        self.assertIn("--candidates speedvaluebcmeldp45", t)

    def test_only_v_adopt_takes_row_b(self):
        t = self._run(REJECT_A, ADOPT_B)
        self.assertIn("--baseline speedvaluebaotouv5", t)
        self.assertIn("--candidates speedvaluebaotouvmeld", t)

    def test_both_reject_takes_row_none(self):
        t = self._run(REJECT_A, REJECT_B)
        self.assertIn("--baseline speedvalue ", t + " ")
        self.assertIn("--candidates speedvaluemeldp45", t)

    def test_mech_warn_on_bc_switches_row_to_b(self):
        # \u2605 R1480 \u7684\u673a\u5236\u95f8\uff1aBC \u8db3\u8ff9\u544a\u8b66 \u21d2 BC \u6309\u4e0d\u91c7\u7528\uff1b\u8fd9\u65f6 V \u5224\u6b63 \u21d2 \u56db\u683c\u5e94\u8d70 B \u884c\u3002\n
        t = self._run(ADOPT_A, ADOPT_B, warn_arm=ARM_A)
        self.assertIn("--baseline speedvaluebaotouv5", t)
        self.assertNotIn("--baseline speedvaluebc", t)


if __name__ == "__main__":
    unittest.main()
