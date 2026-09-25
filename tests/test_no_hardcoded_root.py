# -*- coding: utf-8 -*-
"""★ R1522：`$opsScripts` 里的 **.py 不得把 ROOT 赋成硬编码 `D:\hangzhouMaj`**。

为什么要钉：这些脚本会被强制打进**公开仓**（判卷侧 clone 到任意路径）；
把 ROOT 赋成硬编码绝对路径 ⇒ clone 里直接崩（实测三个：`var/_gate2.py`、`_4test_gate_precheck.py`、`_replay_model.py`）。
正确写法：`ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`。
（注释里提到那条路径不算——只查“真的赋值”。）
"""
from __future__ import annotations
import glob
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
RX_PY = re.compile(r"""ROOT\s*=\s*r?["']D:[\\/]hangzhouMaj""")
RX_PS1 = re.compile(r"""\$Root\s*=\s*["']D:[\\/]hangzhouMaj""")


def code_only(text):
    """⇐ ★ R1538：**只看代码，不看注释**。

    本文件 docstring 早就声明“注释里提到那条路径不算”，但实现没剥注释 ⇒
    R1538 在 `var/_replay_endpoint.py` 修好后、把“原来是硬编码”写进注释，**反而把自己报红了**。
    行级去注释对本检查足够（真正的赋值总在 `#` 之前）。
    """
    out = []
    for ln in (text or "").splitlines():
        i = ln.find("#")
        out.append(ln if i < 0 else ln[:i])
    return "\n".join(out)


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
            if rx.search(code_only(t)):
                bad.append(rel)
        self.assertEqual([], bad,
                         "这些脚本把 ROOT 赋成了硬编码路径 ⇒ clone 里会崩：%s" % bad)


class TestToolsNoHardcodedRoot(unittest.TestCase):
    """★ R1529：`tools/*.py`（会进公开仓）也不得把 `ROOT` 赋成硬编码本机路径。

    实测拉网：`tools/meld_gate_check.py`、`meld_ukeire_cohort.py`、`meld_ukeire_cohort2.py`、`meld_window_split.py` 四个都是
    `ROOT = r'D:\hangzhouMaj'` ⇒ clone 里必崩（而它们不在 `$opsScripts` 里，旧门扫不到）。
    注意：`var/_register_*.ps1` 里的绝对路径是**故意的**（它们生成的就是**本机计划任务定义**）⇒ 不在本门范围。
    """

    def test_tools_derive_root_from_file(self):
        bad = []
        for p in sorted(glob.glob(os.path.join(ROOT, "tools", "*.py"))):
            t = io.open(p, encoding="utf-8", errors="replace").read()
            if RX_PY.search(code_only(t)):
                bad.append(os.path.relpath(p, ROOT).replace("\\", "/"))
        self.assertEqual([], bad, "这些 tools 脚本把 ROOT 赋成了硬编码路径 ⇒ clone 里会崩：%s" % bad)


class TestCommentsDoNotCount(unittest.TestCase):
    """★ R1538：这个门只能报“**真的赋值**”。

    为什么单独钉：R1538 把 `_replay_endpoint.py` 的硬编码修好后，把“原来是硬编码”记进注释，
    **结果被本门误报**（实现里没剥注释，与 docstring 声明不符）。两个方向都要钉住。
    """

    def test_comment_mention_is_not_a_violation(self):
        src = u"# ★ 原：ROOT = r'D:\\hangzhouMaj'\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
        self.assertIsNone(RX_PY.search(code_only(src)), u"注释里提到不算")

    def test_real_assignment_is_still_caught(self):
        self.assertIsNotNone(RX_PY.search(code_only(u"ROOT = r'D:\\hangzhouMaj'\n")))
        self.assertIsNotNone(RX_PY.search(code_only(u'ROOT = "D:/hangzhouMaj"\n')))
        self.assertIsNotNone(RX_PS1.search(code_only(u'$Root = "D:\\hangzhouMaj"\n')))


if __name__ == "__main__":
    unittest.main()