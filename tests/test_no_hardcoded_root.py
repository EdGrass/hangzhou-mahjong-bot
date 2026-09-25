# -*- coding: utf-8 -*-
"""★ R1522：`$opsScripts` 里的 **.py 不得把 ROOT 赋成硬编码 `D:\hangzhouMaj`**。

为什么要钉：这些脚本会被强制打进**公开仓**（判卷侧 clone 到任意路径）；
把 ROOT 赋成硬编码绝对路径 ⇒ clone 里直接崩（实测三个：`var/_gate2.py`、`_4test_gate_precheck.py`、`_replay_model.py`）。
正确写法：`ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`。
（注释里提到那条路径不算——只查“真的赋值”。）
"""
from __future__ import annotations
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
RX_PY = re.compile(r"""ROOT\s*=\s*r?["']D:[\\/]hangzhouMaj""")
RX_PS1 = re.compile(r"""\$Root\s*=\s*["']D:[\\/]hangzhouMaj""")


def _ops_py():
    s = io.open(PS1, encoding="utf-8", errors="replace").read()
    m = re.search(r"\$opsScripts\s*=\s*@\((.*?)\)", s, re.S)
    return [x for x in re.findall(r'"([^"]+)"', m.group(1))
            if x.endswith((".py", ".ps1"))]


@unittest.skipUnless(os.path.exists(PS1), "var/ 不在仓库里（gitignore）")
class TestNoHardcodedRoot(unittest.TestCase):
    def test_ops_scripts_derive_root_from_file(self):
        bad = []
        for rel in _ops_py():
            p = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.exists(p):
                continue
            t = io.open(p, encoding="utf-8", errors="replace").read()
            rx = RX_PS1 if rel.endswith(".ps1") else RX_PY
            if rx.search(t):
                bad.append(rel)
        self.assertEqual([], bad,
                         "这些脚本把 ROOT 赋成了硬编码路径 ⇒ clone 里会崩：%s" % bad)


if __name__ == "__main__":
    unittest.main()