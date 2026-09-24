# -*- coding: utf-8 -*-
"""`var/_verdict_watch.py` 的**判词规则单测**（R1304/R1306 的语义锁死）。

为什么：这个看护是**整条役循环的心跳**（到 80/臂自动出判词），它改错一次就会让役 3 的起役窗口
静默丢失（R1304：旧行为首判即写 sentinel）。本测试把四条语义钉住：

   ① 决定性（rc 0/1）⇒ **写 sentinel**（只出一次）；
   ② 非决定性（rc 2 ⇒ UNDECIDED）⇒ **不写 sentinel**，写进度 marker；
   ③ 所谓“房数不足 / 复盘覆盖 < 70%”（rc 3 但命中这两句）⇒ **不写 sentinel**；
   ④ 到役盒（各臂 ≥ --box-rooms 仍不决定）⇒ 判词文件里必须出现“已达役盒”。

注：`var/` 在 .gitignore 里 ⇒ 仓库克隆后该工具**不存在**，所以本测试 `skipUnless`；
测试用专用 label 并在 tearDown 清理，**不碰** `役2` 的真实产物。
"""
import contextlib
import importlib.util
import io
import os
import shutil
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "var", "_verdict_watch.py")
LABELS = ["自测_w1"]


class _FakeP(object):
    def __init__(self, rc, out):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


@unittest.skipUnless(os.path.exists(TOOL), "var/_verdict_watch.py 不在仓库里（var/ 被 gitignore）")
class TestVerdictWatchRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("vw_t", TOOL)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def tearDown(self):
        for lb in LABELS:
            for pat in ("_verdict_%s.txt" % lb, ".verdict_done_%s" % lb, ".verdict_last_%s" % lb):
                p = os.path.join(ROOT, "var", pat)
                if os.path.exists(p):
                    os.remove(p)

    def _run(self, rc, body, box=120, n=90):
        m = self.m
        prog = {"speedc151": [n, n], "speedvalue": [n, n]}
        argv = ["x", "--label", LABELS[0], "--since", "2026-09-23 03:13:44",
                "--baseline", "speedc151", "--candidate", "speedvalue",
                "--mechanism", "pairs", "--min-rooms", "80", "--box-rooms", str(box)]
        old = sys.argv
        sys.argv = argv
        try:
            with mock.patch.object(m, "progress", return_value=prog), \
                 mock.patch.object(m.subprocess, "run", return_value=_FakeP(rc, body)), \
                 contextlib.redirect_stdout(io.StringIO()):
                m.main()
        finally:
            sys.argv = old
        d = os.path.join(ROOT, "var", ".verdict_done_%s" % LABELS[0])
        mark = os.path.join(ROOT, "var", ".verdict_last_%s" % LABELS[0])
        out = os.path.join(ROOT, "var", "_verdict_%s.txt" % LABELS[0])
        txt = io.open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        return os.path.exists(d), os.path.exists(mark), txt

    def test_decisive_writes_sentinel(self):
        for rc, body in ((0, u"★ 判定：ADOPT speedvalue（和牌率 z=+2.0、番 z=+2.0、护栏通过）"),
                         (1, u"★ 判定：REJECT speedvalue（和牌率 z=-2.0、番 z=-2.0）")):
            sent, mark, _ = self._run(rc, body)
            self.assertTrue(sent, "rc=%d 应写 sentinel" % rc)
            self.assertTrue(mark, "rc=%d 应写进度 marker" % rc)
            self.tearDown()

    def test_undecided_no_sentinel(self):
        sent, mark, txt = self._run(2, u"★ 判定：UNDECIDED（和牌率 z=+1.38、番 z=+1.00）⇒ 继续攒房")
        self.assertFalse(sent, "UNDECIDED 不应写 sentinel（否则永远不再重判）")
        self.assertTrue(mark, "UNDECIDED 应写进度 marker")

    def test_refuse_rooms_or_coverage_no_sentinel(self):
        for body in (u"★ 判定：REFUSE / CONTINUE —— 房数不足（各需 >= 80 房有复盘）",
                     u"★ 判定：REFUSE / CONTINUE —— 复盘覆盖 < 70%（先补拉 tools/fetch_room_replays.py）"):
            sent, _, _ = self._run(3, body)
            self.assertFalse(sent, "房数/覆盖不足属非决定性，不应写 sentinel")
            self.tearDown()

    def test_box_marks_verdict(self):
        sent, _, txt = self._run(2, u"★ 判定：UNDECIDED（和牌率 z=+1.20、番 z=+0.90）⇒ 继续攒房", box=10)
        self.assertFalse(sent)
        self.assertIn(u"已达役盒", txt, "到役盒时判词文件必须标注")

    def test_box_below_threshold_not_marked(self):
        _, _, txt = self._run(2, u"★ 判定：UNDECIDED（z=+1.20）⇒ 继续攒房", box=1000)
        self.assertNotIn(u"已达役盒", txt)
