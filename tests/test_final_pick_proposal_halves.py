# -*- coding: utf-8 -*-
"""★ R1549：10/5 提案必须**自己把两半 Pareto 跑出来**。

为什么：R1501/R1505 已实测「主序列 MDE≈41 分，而臂间差 22~38」⇒ `_pick_arm` 几乎必然报
“不可区分”，而它只会**叫人去跑**两半 Pareto —— 万一没跑，10/5 的人工选臂就是在**没有真判据**
的情况下做的。本文件钉住：命令对、顺序对、必走 lowprio、且真的接进主流程。
"""
from __future__ import annotations
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _final_pick_proposal as M  # noqa: E402


class _P(object):
    def __init__(self, out):
        self.stdout = out
        self.stderr = ""


class TestHalvesCmds(unittest.TestCase):
    def test_two_steps_in_order(self):
        steps = M.halves_cmds("2026-09-25 20:52:39", 32)
        self.assertEqual(2, len(steps))
        self.assertTrue(steps[0][0].startswith("half-A"))
        self.assertTrue(steps[1][0].startswith("half-B"))
        for _, cmd in steps:
            self.assertIn("_lowprio_run.py", " ".join(cmd))
            self.assertIn("--since", cmd)
            self.assertIn("--by-arm", cmd)

    def test_half_b_carries_top(self):
        _, cmd = M.halves_cmds("T", 32)[1]
        self.assertIn("--top", cmd)
        self.assertIn("32", cmd)
        self.assertIn("_seat_h2h.py", " ".join(cmd))

    def test_half_a_targets_hu_gap_split(self):
        _, cmd = M.halves_cmds("T", 32)[0]
        self.assertIn("hu_gap_split.py", " ".join(cmd))
        self.assertIn("recent", cmd)


class TestHalvesSection(unittest.TestCase):
    def test_section_prints_header_and_both_outputs(self):
        seen = []

        def runner(cmd):
            seen.append(" ".join(cmd))
            return _P("STUB-OUT-%d" % len(seen))

        out = M.halves_section("T", 32, runner=runner)
        self.assertIn(u"两半 Pareto", out)
        self.assertIn(u"真正判据", out)
        self.assertIn("half-A", out)
        self.assertIn("half-B", out)
        self.assertIn("STUB-OUT-1", out)
        self.assertIn("STUB-OUT-2", out)
        self.assertEqual(2, len(seen))
        self.assertTrue(all("_lowprio_run.py" in s for s in seen), seen)

    def test_runner_error_is_reported_not_raised(self):
        def runner(cmd):
            raise RuntimeError("boom")
        out = M.halves_section("T", 32, runner=runner)
        self.assertIn(u"跑不动", out)

    def test_wired_into_main(self):
        with io.open(os.path.join(ROOT, "var", "_final_pick_proposal.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("halves_section(started", s)


if __name__ == "__main__":
    unittest.main()

class TestDeployStatusR1567(unittest.TestCase):
    """★ R1567：提案里必须把“哪些臂**可部署**”标出来 —— 回退窗口会把旧臂混进同一张表，
    实测（2026-09-26）主序列第一名就是一个从未判正的臂。"""

    def test_marks_only_adopted_arms(self):
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_arm_confirm as C
        d = tempfile.mkdtemp(prefix="r1567_")
        p = os.path.join(d, "_verdict_役2.txt")
        io.open(p, "w", encoding="utf-8").write(
            u"=== 役：speedc151（基线） vs speedvalue（候选）  since=1\n"
            u"★ 判定：ADOPT speedvalue（和牌率 z=+1.83）\n")
        vs = C.load_verdicts([p])
        st = M.deploy_status(["speedvalue", "speedvaluebc"], vs)
        self.assertTrue(st["speedvalue"])
        self.assertFalse(st["speedvaluebc"])
        out = M.deploy_section(["speedvalue", "speedvaluebc"], vs)
        self.assertIn(u"✅", out)
        self.assertIn(u"不可部署", out)
        self.assertIn(u"§V.161 A.1", out)

