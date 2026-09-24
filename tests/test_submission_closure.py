# -*- coding: utf-8 -*-
"""**提交包闭包门**（R1345）：清单里的运行期脚本必须“自包含”。

为什么（本轮实测的真缺口）：`var/` 被 `.gitignore` 忽略，运行期脚本只能靠
`_prepare_submission.ps1` 里的 `$opsScripts` **逐个 `git add -f`**。漏一个，clone 出来就是“看着完整、其实断链”：
实例：`var/_ensure_all.py` 在公网副本里 `import` 同级模块 `_feature_mode`
⇒ **全部相关单测 `ModuleNotFoundError`**（而本机因为 var/ 里什么都有，**永远不会发现**）。

本门用**静态图**钉死：把 `$opsScripts` 当种子，沿两种引用边扩张到闭包 ——
  ① `import X` / `from X import`（X 是 var/ 里的同级模块）；
  ② 源码里按**路径**出现的 `var/\u2026.py`（动态 import / subprocess / 任务注册都走这条）。
然后断言：**闭包 ⊆清单**（不允许“清单引用了清单外的 var/ 文件”），且清单内每个文件都**已被 git 追踨**。
"""
import io
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
RX_IMP = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.M)
RX_PATH = re.compile(r"(var[\\/][A-Za-z_0-9\u4e00-\u9fff.]+\.(?:py|ps1))")


def ops_list():
    """从 `$opsScripts = @( \u2026 )` 里把清单读出来（以“真正被 add 的那份清单”为准）。"""
    with io.open(PS1, encoding="utf-8-sig") as f:
        s = f.read()
    m = re.search(r"\$opsScripts\s*=\s*@\((.*?)\)", s, re.S)
    if not m:
        return []
    return [x.replace("\\", "/") for x in re.findall(r'"([^"]+)"', m.group(1))]


@unittest.skipUnless(os.path.exists(PS1), "var/ 不在仓库里（gitignore）")
class TestSubmissionClosure(unittest.TestCase):
    def test_list_is_nonempty(self):
        ops = ops_list()
        self.assertGreaterEqual(len(ops), 20, "清单解析失败（否则本门是空跑）：%s" % ops)

    def test_closure_inside_list(self):
        ops = set(ops_list())
        sib = set(f[:-3] for f in os.listdir(os.path.join(ROOT, "var"))
                  if f.endswith(".py"))
        seen, queue = set(), [os.path.basename(x)[:-3] for x in sorted(ops) if x.endswith(".py")]
        while queue:
            m = queue.pop(0)
            if m in seen:
                continue
            seen.add(m)
            p = os.path.join(ROOT, "var", m + ".py")
            if not os.path.exists(p):
                continue
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                src = f.read()
            for a, b in RX_IMP.findall(src):
                n = (a or b).split(".")[0]
                if n in sib and n not in seen:
                    queue.append(n)
            for r in RX_PATH.findall(src):
                r = r.replace("\\", "/")
                if r.endswith(".py") and r not in ops:
                    n = os.path.basename(r)[:-3]
                    if n in sib and n not in seen:
                        queue.append(n)
        leaked = sorted("var/%s.py" % m for m in seen if ("var/%s.py" % m) not in ops)
        self.assertEqual([], leaked,
                         "以下 var/ 文件在清单的**依赖闭包**里但**不在清单上** ⇒ clone 里会缺文件（用 -Go 前必须先补进 $opsScripts）：%s" % leaked)

    def test_listed_files_are_tracked(self):
        try:
            tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                         text=True, timeout=60).stdout.split())
        except Exception as e:
            self.skipTest("git 不可用：%s" % e)
        if not tracked:
            self.skipTest("未取到 git 跟踨列表")
        untracked = [f for f in ops_list() if f not in tracked]
        self.assertEqual([], untracked,
                         "以下文件在 $opsScripts 里但**尚未入仓** ⇒ 跑 `_prepare_submission.ps1 -Go` 后必须先 commit 再 push：%s" % untracked)


if __name__ == "__main__":
    unittest.main()
