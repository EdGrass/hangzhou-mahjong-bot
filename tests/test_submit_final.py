# -*- coding: utf-8 -*-
"""var/_submit_final.py 的单测（门禁纯函数 + 编码兜底 + 接线）。

为什么要钉：这是**唯一一个硬截止（10/8 12:00）**的自动化。它错了的后果是"没交上"或"交了坏东西"，
所以门禁必须 fail-closed，且"不该提交时绝不碰 git"。
"""
from __future__ import annotations
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _submit_final as S  # noqa: E402


class TestGate(unittest.TestCase):
    def test_abort_when_check_fails(self):
        act, why = S.gate(1, False)
        self.assertEqual("abort", act)
        self.assertIn("rc=1", why)

    def test_go_when_check_ok(self):
        self.assertEqual("go", S.gate(0, False)[0])

    def test_noop_when_marker_present(self):
        # marker 优先于一切（幂等）：即便检查失败也不再提交
        self.assertEqual("noop", S.gate(0, True)[0])
        self.assertEqual("noop", S.gate(1, True)[0])

    def test_abort_on_other_rc(self):
        for rc in (2, 3, -1):
            self.assertEqual("abort", S.gate(rc, False)[0], rc)


class TestDecode(unittest.TestCase):
    def test_utf8(self):
        self.assertEqual("中文 ok", S._dec("中文 ok".encode("utf-8")))

    def test_gbk_fallback(self):
        # 任务上下文实测：PowerShell 5.1 输出是 GBK ⇒ 必须能读回来（否则日志全乱码）
        self.assertEqual("提交物检查 rc=1", S._dec("提交物检查 rc=1".encode("gbk")))

    def test_broken_bytes_do_not_raise(self):
        self.assertIsInstance(S._dec(b"\xff\xfe\x00abc"), str)


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_submit_final.py")),
                     "var/ 不在仓库里（gitignore）")
class TestWiring(unittest.TestCase):
    def test_three_steps_in_order(self):
        with io.open(os.path.join(ROOT, "var", "_submit_final.py"), encoding="utf-8-sig") as f:
            src = f.read()
        i_gate = src.index("act, why = gate(")
        i_prep = src.index('"-File", PS1, "-Go"')
        i_push = src.index('"push", "origin", "HEAD:main"')
        self.assertLess(i_gate, i_prep, "门禁必须在 -Go 之前")
        self.assertLess(i_prep, i_push, "推送必须在准备提交物之后")
        self.assertIn("_prepare_submission.ps1", src)
        self.assertIn("GIT_TERMINAL_PROMPT", src)

    def test_post_check_requires_sync(self):
        with io.open(os.path.join(ROOT, "var", "_submit_final.py"), encoding="utf-8-sig") as f:
            src = f.read()
        self.assertIn("origin/main...HEAD", src, "必须校验 本地==origin/main")
        self.assertIn(".final_submitted", src)


if __name__ == "__main__":
    unittest.main()
