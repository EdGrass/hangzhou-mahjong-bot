# -*- coding: utf-8 -*-
"""★ R1500b：**行尾守卫** —— 防止“整文件 churn”（改两行 ⇒ diff 千行）。

为什么要钉：本会话我**三次**把行尾整体改掉（`var/_prepare_submission.ps1` 414 行、
两个 test 文件、`docs/正式赛执行清单` 822 行），每次都造成“改了两行、diff 千行”。
人会忘，所以用**机器拦**（在回归门里；边界见文末）：凡被改动的文本文件，其“CRLF 占比”**不得从一端翻到另一端**。

三个实现陷阱（初版全踩了，写在这里防复犯）：
1. `subprocess(text=True)` 读 `git show` ⇒ **universal newlines 会把 CRLF 折成 LF** ⇒ HEAD 侧恒 0%，
   每个 CRLF 文件都被误报。必须走**字节**（`git cat-file blob`）。
2. 字节字面量里的转义写成真换行 ⇒ **文件本身语法错误**，守卫连 import 都过不了。
   ⇒ 守卫自己必须先能跑（`python -X utf8 -m unittest tests.test_line_endings`），这是它的下限。
3. `git diff --name-only` 不带 `-z` / `core.quotePath=false` ⇒ **非 ASCII 路径被打印成八进制转义**
   （`"docs\\346\\255\\243..."`）且首尾带引号 ⇒ 按空白切分后**后缀不是 `.md`** ⇒
   `docs/正式赛执行清单-一个月后.md` 这类中文路径会被**静默跳过**，守卫看着绿其实没看它。

局限（诚实写明）：它只能在**有未提交改动时**生效。一旦翻转已经被提交，随后的“恢复”在它眼里
也是一次翻转。所以它的作用是**在你准备 commit 之前叫住你**。

边界（有意为之）：它只在**回归门**（`unittest discover`）里生效，**没有**接进
`var/_prepare_submission.ps1` —— 10/8 10:00 是硬截止，装饰性的行尾问题不该把
fail-closed 的提交流程挡死。⇒ 提交前仍要跑全量回归（至少跑这条）。
"""
from __future__ import annotations

import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_EXT = (".py", ".md", ".ps1", ".json", ".txt", ".jsonl", ".toml", ".js", ".ts", ".html", ".csv", ".tsv")


def _git_bytes(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True)


def _changed_paths():
    """相对 HEAD 已改动的路径列表（失败 ⇒ (None, stderr)）。"""
    r = _git_bytes("-c", "core.quotePath=false", "diff", "--name-only", "-z", "HEAD")
    if r.returncode != 0:
        return None, r.stderr
    return [x for x in r.stdout.decode("utf-8", "replace").split("\0") if x], b""


def _crlf_share(blob):
    """CRLF 行数 / LF 行数；无换行（空文件 / 二进制）⇒ None（不判）。"""
    lf = blob.count(b"\n")
    return (blob.count(b"\r\n") / lf) if lf else None


class TestLineEndings(unittest.TestCase):
    def test_no_wholesale_lineending_flip(self):
        changed, err = _changed_paths()
        if changed is None:
            self.skipTest("非 git 工作区（%s）" % (err or b"")[:60])
        bad = []
        for rel in changed:
            if not rel.lower().endswith(TEXT_EXT):
                continue
            path = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.exists(path):
                continue                       # 删除的文件不管
            old = _git_bytes("cat-file", "blob", "HEAD:" + rel)
            if old.returncode != 0:
                continue                       # 新增文件无历史版本
            with open(path, "rb") as f:
                nb = f.read()
            a, c = _crlf_share(old.stdout), _crlf_share(nb)
            if a is None or c is None:
                continue
            if (a > 0.5) != (c > 0.5):
                bad.append("%s（HEAD CRLF %.0f%% → 工作区 %.0f%%）" % (rel, 100 * a, 100 * c))
        self.assertEqual([], bad,
                         "行尾整体翻转 ⇒ 会造成整文件 churn。请用与原文件相同的 newline 写回：%s" % bad)


class TestChangedPaths(unittest.TestCase):
    def test_non_ascii_paths_survive(self):
        """★ 回归（陷阱 3）：非 ASCII 路径必须原样可见、且不含反斜杠转义。"""
        sample = "docs/正式赛执行清单-一个月后.md\0bot/a b.py\0"
        paths = [x for x in sample.split("\0") if x]
        self.assertEqual(2, len(paths))
        self.assertTrue(paths[0].endswith(".md"), paths[0])
        self.assertTrue(all("\\" not in x for x in paths), paths)


if __name__ == "__main__":
    unittest.main()