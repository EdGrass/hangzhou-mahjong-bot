# -*- coding: utf-8 -*-
"""`.ps1` 编码门（R1323）：含非 ASCII 的 `.ps1` **必须**带 UTF-8 BOM。

为什么：**Windows PowerShell 5.1** 对无 BOM 的文件按 **ANSI(GBK)** 解码 ⇒
中文串 mojibake、甚至直接语法错误。实测（2026-09-24）：
  * `var/_switch_to_official.ps1` 带 BOM 时 5.1 解析 0 错；某次用 Python 重写后丢了 BOM ⇒ 5.1 报 2 个错；
  * 而 `tests/test_switch_official.py` 用 `shutil.which("powershell") or shutil.which("pwsh")` ⇒ 优先拿到 5.1 ⇒ **单测变红**（而 pwsh 7 一直正常）。

本门是**纯字节级**检查（不需要 PowerShell，Linux/CI 也跑），只针对仓库内的 `.ps1`。
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "replays", "logs", "__pycache__", ".venv", "venv", "node_modules"}


def _ps1_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower().endswith(".ps1"):
                out.append(os.path.join(dirpath, fn))
    return out


class TestPs1Encoding(unittest.TestCase):
    def test_non_ascii_ps1_must_have_bom(self):
        bad = []
        for p in _ps1_files():
            with open(p, "rb") as f:
                b = f.read()
            if any(x > 127 for x in b) and not b.startswith(b"\xef\xbb\xbf"):
                bad.append(os.path.relpath(p, ROOT))
        self.assertEqual(bad, [], "以下 .ps1 含非 ASCII 但无 UTF-8 BOM（PowerShell 5.1 会按 GBK 读）：%s" % bad)

    def test_scan_finds_some_files(self):
        files = _ps1_files()
        self.assertTrue(files, "应至少找到一个 .ps1（否则本门是空跑）")
