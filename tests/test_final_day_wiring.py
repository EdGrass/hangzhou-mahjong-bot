# -*- coding: utf-8 -*-
"""10/7 换臂链的**接线门**（R1436）。

为什么要这门外加一层：本轮的第一次接线就插错了位置 —— 新增的两行被放进了**头部注释**
（`findIndex` 命中了注释里的 "HangzhouMajFinalCheck2"），而 `_ps_syntax_check.ps1` 照样
报 "syntax OK"：插错位置属于"语法合法、语义全错"。同一轮还踩了第二个坑：**新 .ps1 没写 BOM**
⇒ PS 5.1 按 ANSI 解码中文注释 ⇒ 把后面的 `param` 块吃掉 ⇒ `$Root` 为 null。

这门外加两条静态断言把两件事都钉死：
  ① 注册语句必须**真的调用注册函数**（在行首、且参数写对），不是只在注释里提到；
  ② 带中文的 .ps1 必须**带 BOM**，且 `param` 之前不许有执行语句。
"""
from __future__ import annotations
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "var", "_register_final_day.ps1")
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
RETRY = os.path.join(ROOT, "var", "_final_switch_retry.ps1")
CONFIRM = os.path.join(ROOT, "var", "_final_arm_confirm.py")


def read(p):
    with io.open(p, encoding="utf-8-sig") as f:
        return f.read()


def read_raw(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


@unittest.skipUnless(os.path.exists(REG), "var/ 不在仓库里（gitignore）")
class TestFinalDayWiring(unittest.TestCase):
    def test_confirm_task_really_registered(self):
        s = read(REG)
        self.assertRegex(
            s,
            r'(?m)^Reg-One\s+"HangzhouMajFinalArmConfirm"\s+"2026-10-07 08:30:00"\s+"_final_arm_confirm\.py"',
            "HangzhouMajFinalArmConfirm 必须真的被 Reg-One 注册（行首调用，不能只在注释里）")

    def test_retry_task_really_registered(self):
        s = read(REG)
        self.assertIn('$retryName = "HangzhouMajFinalSwitchRetry"', s)
        self.assertRegex(s, r'Register-ScheduledTask -TaskName \$retryName',
                        "换臂重试必须真的 Register-ScheduledTask")
        self.assertIn('"2026-10-07 12:00:00"', s)
        self.assertIn("-WindowStyle Hidden", s, "后台任务不得弹窗")

    def test_param_is_first_statement(self):
        """param 之前只允许注释/空行 —— 否则 PS 会忽略默认值（本轮真实踩过）。"""
        lines = read(REG).splitlines()
        pi = next(i for i, l in enumerate(lines) if l.strip().startswith("param("))
        for l in lines[:pi]:
            t = l.strip()
            self.assertTrue(t == "" or t.startswith("#"),
                            "param 之前出现了语句：%r" % l)

    def test_new_files_in_closure_list(self):
        s = read(PS1)
        self.assertIn('"var/_final_arm_confirm.py"', s)
        self.assertIn('"var/_final_switch_retry.ps1"', s)

    def test_ps1_files_have_bom(self):
        """中文注释的 .ps1 必须带 BOM（PS 5.1 否则按 ANSI 解码，会吃掉 param 块）。"""
        for p in (REG, RETRY):
            self.assertTrue(read_raw(p).startswith("\ufeff"),
                            "%s 缺 BOM" % os.path.basename(p))

    def test_wrapper_is_rehearsable(self):
        """包装脚本必须能随时排练（-DryRun 全链路 --dry-run），否则只能等 10/7 才能验。"""
        s = read(RETRY)
        self.assertIn("[switch]$DryRun", s)
        self.assertIn("--dry-run", s)
        self.assertIn("--go", s)
        self.assertIn("_final_arm_confirm.py", s)
        self.assertIn("_switch_final.py", s)


@unittest.skipUnless(os.path.exists(CONFIRM), "var/ 不在仓库里（gitignore）")
class TestConfirmScriptInvariants(unittest.TestCase):
    def test_never_writes_arm_without_instantiation_check(self):
        """落盘前必须有 arm_ok 校验，且失败路径 return 2（顺序：校验在写之前）。"""
        s = read(CONFIRM)
        i_ok = s.index("ok, why = arm_ok(arm)")
        i_w = s.index('with io.open(a.out, "w"')
        self.assertLess(i_ok, i_w, "实例化校验必须在写入之前")
        self.assertIn("if not ok:", s[:i_w + 200])

    def test_refresh_cannot_downgrade(self):
        s = read(CONFIRM)
        self.assertIn("不降级", s)
        self.assertIn("--refresh", s)


if __name__ == "__main__":
    unittest.main()
