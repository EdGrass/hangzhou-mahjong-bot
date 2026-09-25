# -*- coding: utf-8 -*-
"""★ R1536：`_lowprio_run.py` 在 **pythonw（计划任务）** 下必须把子进程输出转发出来。

为什么（生产实测，不是洁癖）：计划任务用 `pythonw.exe` 起 `_mech_watch.py`，它再经
`_lowprio_run.py` 跑 `_seat_h2h.py --by-arm`。只靠“句柄继承”时**孙进程的输出会整段丢掉**，
`_mech_watch.log` 连出两次：

    !! V 机制读数（_seat_h2h）解析为空：rc=0 stdout=191 字

而那 191/176 字**正好只有 `_lowprio_run` 的 banner**（真表 3600+ 字）⇒ **V 轴的机制读数永远拿不到**
⇒ V 既判不出 PASS 也判不出 FAIL（只能 UNKNOWN）⇒ 一旦四格由 V 决定（R1534 的 fail-closed）就**停摆**。

本文件在**真·pythonw 父进程**里复现计划任务的形状（python.exe 下继承是好的 ⇒ 复现不出来）。
"""
from __future__ import annotations
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

PROBE = u"""# -*- coding: utf-8 -*-
import io, os, subprocess, sys
out, root = sys.argv[1], sys.argv[2]
low = os.path.join(root, "var", "_lowprio_run.py")
p = subprocess.run([sys.executable, "-X", "utf8", low, "--",
                    sys.executable, "-c", "print('MA'+'RK-ZZZ')"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
with io.open(out, "w", encoding="utf-8") as f:
    f.write("rc=%s" % p.returncode)
    f.write(chr(10))
    f.write(p.stdout or "")
"""


@unittest.skipUnless(os.name == "nt" and os.path.exists(PYW), "需要 Windows + pythonw.exe")
class TestLowprioRunUnderPythonw(unittest.TestCase):
    def test_grandchild_stdout_reaches_the_pipe(self):
        d = tempfile.TemporaryDirectory()
        try:
            probe = os.path.join(d.name, "probe.py")
            out = os.path.join(d.name, "out.txt")
            with io.open(probe, "w", encoding="utf-8") as f:
                f.write(PROBE)
            r = subprocess.run([PYW, "-X", "utf8", probe, out, ROOT],
                               capture_output=True, text=True, timeout=300)
            self.assertTrue(os.path.exists(out), "探针没写出结果：rc=%s err=%s" % (r.returncode, (r.stderr or "")[:200]))
            body = io.open(out, encoding="utf-8").read()
            # ★ 关键断言：必须有一**整行**恰好是 `MARK-ZZZ`。
            #   不能只判子串 —— banner 里就带着 `print('MA'+'RK-ZZZ')`，子串会假阳性。
            lines = [x.strip() for x in body.splitlines()]
            self.assertIn(u"MARK-ZZZ", lines,
                          u"pythonw 下吞掉了子进程输出（只剩 banner）⇒ V 机制读数会永远为空：\n" + body[:400])
        finally:
            d.cleanup()

    def test_source_forwards_handles_explicitly(self):
        s = io.open(os.path.join(ROOT, "var", "_lowprio_run.py"), encoding="utf-8").read()
        self.assertIn(u'kw["stdout"] = sys.stdout', s)
        self.assertIn(u'kw["stderr"] = sys.stderr', s)
        self.assertIn(u"subprocess.call(cmd, **kw)", s)


if __name__ == "__main__":
    unittest.main()
