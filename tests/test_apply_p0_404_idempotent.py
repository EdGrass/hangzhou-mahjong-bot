# -*- coding: utf-8 -*-
"""R1590：P0 v35 补丁器必须幂等。

现场：代码已经是 v35（protocol.py 新分支 + __init__.py=35），但 `_bsegment` 每次切换
都会无条件跑 `_apply_p0_404.py --go`；旧实现发现 `=34` 消失就 rc=2 ⇒ 役间自动切换
卡死在 P0 步骤。这个测试先钉住“已应用时 --check 必须成功”。
"""
from __future__ import annotations
import importlib.util
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    path = os.path.join(ROOT, "var", "_apply_p0_404.py")
    spec = importlib.util.spec_from_file_location("apply_p0_404_t", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["apply_p0_404_t"] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


class TestApplyP0Idempotent(unittest.TestCase):
    def test_check_accepts_already_patched_files(self):
        with tempfile.TemporaryDirectory() as d:
            prot = os.path.join(d, "protocol.py")
            init = os.path.join(d, "__init__.py")
            with io.open(prot, "w", encoding="utf-8", newline="") as f:
                f.write(m.NEW_404)
            with io.open(init, "w", encoding="utf-8", newline="") as f:
                f.write("GUIDE_VERSION_KNOWN = 35\n")

            old_prot, old_init = m.PROT, m.INIT
            old_argv = sys.argv
            m.PROT, m.INIT = prot, init
            sys.argv = ["_apply_p0_404.py", "--check"]
            try:
                rc = m.main()
            finally:
                m.PROT, m.INIT = old_prot, old_init
                sys.argv = old_argv
            self.assertEqual(0, rc)


if __name__ == "__main__":
    unittest.main()