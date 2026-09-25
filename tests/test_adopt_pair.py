# -*- coding: utf-8 -*-
"""`var/_adopt_pair.py` 的单测（纯函数）。

为什么要钉：这是**唯一**能把役 3 推进到役 4 的自动化（`_bsegment` 只注册判词看护，
`HangzhouMajAdoptWatch` 只盯役 2 ⇒ 没人判就**静默停摆**）。它判错一次 = 起错役、白烧 1.7 天。
四格映射必须与役 3 读卡 §3 逐字一致；"无法判定"必须**原地不动**而不是猜。
R1480 起它还要把预登记 **B3（机制不达标 ⇒ 本役作废）**接上：
`_mech_watch` 写的 `var/.mech_warn` 以前**无人读** ⇒ 机制坏了也会被采用。
"""
from __future__ import annotations
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _adopt_pair as AP  # noqa: E402

ADOPT_BC = "ADOPT speedvaluebc（和牌率 z=+1.80、番 z=+1.60、护栏通过）"
ADOPT_V = "ADOPT speedvaluebaotouv5（和牌率 z=+1.55、番 z=+1.70、护栏通过）"


class TestLines(unittest.TestCase):
    def test_is_adopt_real_format(self):
        self.assertTrue(AP.is_adopt(ADOPT_BC))
        self.assertTrue(AP.is_adopt(ADOPT_V))
        for t in ("REFUSE / CONTINUE —— 第一率护栏未过", "REJECT speedvalue（和牌率 z=-2.1）",
                  "UNDECIDED（和牌率 z=+0.9）⇒ 继续攒房", ""):
            self.assertFalse(AP.is_adopt(t), t)

    def test_last_verdict_wins(self):
        t = "★ 判定：REFUSE 旧\n★ 判定：ADOPT speedvaluebc\n"
        self.assertTrue(AP.is_adopt(AP.last_verdict(t)))


class TestClassify(unittest.TestCase):
    def test_adopt_ok(self):
        self.assertEqual((True, "x"), (AP.classify_candidate(ADOPT_BC, 0)[0], "x"))

    def test_adopt_unknown_does_not_block(self):
        # §7.3/§8：样本不足 ⇒ 只记录、不据此翻转 ⇒ 仍算采用
        self.assertTrue(AP.classify_candidate(ADOPT_BC, 2)[0])

    def test_adopt_veto_blocks(self):
        # §7.2/§8：强手房/决赛相似层显著劣 ⇒ 不采用
        self.assertFalse(AP.classify_candidate(ADOPT_BC, 3)[0])

    def test_adopt_tool_error_is_undecidable(self):
        # 工具异常（rc=1 等）⇒ 必须"无法判定"，绝不当成采用或不采用
        self.assertIsNone(AP.classify_candidate(ADOPT_BC, 1)[0])
        self.assertIsNone(AP.classify_candidate(ADOPT_BC, None)[0])

    def test_non_adopt_never_needs_veto(self):
        for line in ("REFUSE / CONTINUE —— 第一率护栏未过",
                     "REJECT speedvalue（和牌率 z=-2.1）",
                     "UNDECIDED（和牌率 z=+1.27）"):
            self.assertFalse(AP.classify_candidate(line, None)[0], line)


class TestFourCell(unittest.TestCase):
    """四格必须与役 3 读卡 §3 一致：BC✓ ⇒ A 行（无论 V）；BC✗ 且 V✓ ⇒ B 行；都 ✗ ⇒ NONE 行。"""

    def test_rows(self):
        self.assertEqual("a", AP.pick_row(True, True))
        self.assertEqual("a", AP.pick_row(True, False))
        self.assertEqual("b", AP.pick_row(False, True))
        self.assertEqual("none", AP.pick_row(False, False))


class TestMechState(unittest.TestCase):
    """R1480：预登记 B3 在采用路径上的读数（用临时文件，不碰真实 `var/.mech_warn`）。"""

    def setUp(self):
        import tempfile
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, ".mech_warn")
        self.since = "2026-09-25 20:52:39"

    def tearDown(self):
        self.d.cleanup()

    def _write(self, text, mtime=None):
        with io.open(self.p, "w", encoding="utf-8") as f:
            f.write(text)
        if mtime is not None:
            os.utime(self.p, (mtime, mtime))

    def test_no_warn_is_ok(self):
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_warn_naming_arm_is_fail(self):
        self._write(u"2026-09-25 21:00:00 speedvaluebc draw 足迹 6.2%/action 0.0% 脱离预期\n")
        st, why = AP.mech_state("speedvaluebc", self.since, path=self.p)
        self.assertEqual("fail", st)
        self.assertIn("speedvaluebc", why)

    def test_warn_naming_other_arm_is_ok(self):
        self._write(u"2026-09-25 21:00:00 speedvaluebaotouv5 draw 足迹 22.0%/action 0.0% 脱离预期\n")
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_stale_warn_before_window_is_ok(self):
        # 告警时间早于本役起点 ⇒ 陈旧，不得误伤
        import datetime as dt
        old = dt.datetime(2026, 9, 20, 10, 0, 0).timestamp()
        self._write(u"2026-09-20 10:00:00 speedvaluebc …\n", mtime=old)
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_unreadable_is_unknown(self):
        # 路径是目录 ⇒ 读不出 ⇒ unknown（调用方必须原地不动）
        self.assertEqual("unknown", AP.mech_state("speedvaluebc", self.since, path=self.d.name)[0])


if __name__ == "__main__":
    unittest.main()
