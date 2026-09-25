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
import json
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
        # ★ R1534：V 的机制读数（`VREC`）与停摆标记（`VSTALL_OUT`）也必须改指临时路径，
        #   否则接线测试会读到**真实的** `var/_v_mech_readings.jsonl`、并可能写真实标记。
        self._old = (AP.B2_OUT, AP.CONFLICT_OUT, AP.VREC, AP.VSTALL_OUT)
        AP.B2_OUT = os.path.join(self.d.name, ".B2_CANDIDATES")
        AP.CONFLICT_OUT = os.path.join(self.d.name, ".VERDICT_RULE_CONFLICT")
        AP.VSTALL_OUT = os.path.join(self.d.name, ".ADOPT_V_MECH_STALL")
        AP.VREC = os.path.join(self.d.name, "_v_mech_readings.jsonl")
        self.marker = AP.VSTALL_OUT
        self._paths = []
        for suf in ("bc", "v"):
            for pre in (".verdict_done_", "_verdict_"):
                p = os.path.join(ROOT, "var", pre + LABEL + suf + (".txt" if pre == "_verdict_" else ""))
                self._paths.append(p)

    def tearDown(self):
        (AP.B2_OUT, AP.CONFLICT_OUT, AP.VREC, AP.VSTALL_OUT) = self._old
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

    def _vrec(self, state):
        """★ R1534：写一条 V 的机制读数（`pass` / `fail` / `unknown`）。

        采用闸只在四格**由 V 决定**（row=b）时读它 ⇒ 走 B 行的用例必须声明 `pass`。
        """
        ok = {"pass": True, "fail": False, "unknown": None}[state]
        rec = {"ts": "2026-09-25 21:00:00", "arm": ARM_B, "baseline": "speedvalue",
               "ok": ok, "why": u"自测：" + state}
        _w(AP.VREC, json.dumps(rec, ensure_ascii=False) + u"\n")

    def _run(self, line_a, line_b, warn_text=None, warn_arm=None,
             v_mech="pass", dry_run=True):
        self._fixture(line_a, line_b)
        self._vrec(v_mech)
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
            argv = ["x", "--label", LABEL, "--baseline", "speedvalue",
                    "--since", "2026-09-25 20:52:39"]
            if dry_run:
                argv.append("--dry-run")
            with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", out):
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
        # ★ R1535：B2 标记必须**记下本役窗口** —— 否则 10/5 提案拿到臂名也不知道用哪个 --since，
        #   预登记要求的“与 §V.66 口径并行比较”就没法做。
        b2 = io.open(AP.B2_OUT, encoding="utf-8").read()
        self.assertIn(u"窗口 since=2026-09-25 20:52:39", b2)

    def test_v_mech_fail_downgrades_row_to_none(self):
        """★ R1534：V 被 gate2 判正、但机制读数**明确不达标** ⇒ 按 B3 作废 ⇒ 回 NONE 行。"""
        t = self._run(REJECT_A, ADOPT_B, v_mech="fail")
        self.assertIn("--baseline speedvalue ", t + " ")
        self.assertIn("--candidates speedvaluemeldp45", t)
        self.assertNotIn("--baseline speedvaluebaotouv5", t)

    def test_v_mech_unknown_stalls_and_writes_marker(self):
        """★ R1534：V 的机制**读不出**而现在要靠 V 决定四格 ⇒ 原地不动 + 落停摆标记。

        这是修掉的那个 fail-open 的反面：以前这里会**直接起役 4 的 B 行**。
        """
        t = self._run(REJECT_A, ADOPT_B, v_mech="unknown", dry_run=False)
        self.assertNotIn("--baseline", t)           # 不许打印任何起役命令
        self.assertIn(u"fail-closed", t)
        self.assertTrue(os.path.exists(self.marker), u"应落 .ADOPT_V_MECH_STALL")
        body = io.open(self.marker, encoding="utf-8").read()
        self.assertIn(u"raw row = b", body)

    def test_dry_run_never_writes_the_stall_marker(self):
        # ★ R1534：dry-run 零副作用（与 `_mech_watch --dry-run` 同一条纪律）
        t = self._run(REJECT_A, ADOPT_B, v_mech="unknown", dry_run=True)
        self.assertIn(u"fail-closed", t)
        self.assertFalse(os.path.exists(self.marker), u"dry-run 不得写标记")

    def test_mech_warn_on_bc_switches_row_to_b(self):
        # \u2605 R1480 \u7684\u673a\u5236\u95f8\uff1aBC \u8db3\u8ff9\u544a\u8b66 \u21d2 BC \u6309\u4e0d\u91c7\u7528\uff1b\u8fd9\u65f6 V \u5224\u6b63 \u21d2 \u56db\u683c\u5e94\u8d70 B \u884c\u3002\n
        t = self._run(ADOPT_A, ADOPT_B, warn_arm=ARM_A)
        self.assertIn("--baseline speedvaluebaotouv5", t)
        self.assertNotIn("--baseline speedvaluebc", t)


if __name__ == "__main__":
    unittest.main()
