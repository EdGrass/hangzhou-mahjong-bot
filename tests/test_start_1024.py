# -*- coding: utf-8 -*-
"""`var/_start_1024.ps1` 手工开赛入口的回归测试。

背景：该脚本曾长期写死 `speedc068lo0`，而按真机逐轮口径它是历史最差档。
2026-09-17 的二测使用 `speedc151`（5 房 A/B 净胜 +222.7/房，t=2.68），
因此手工入口必须与自动化切换入口使用同一已验证策略，不能再留旧默认值。
"""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "var", "_start_1024.ps1")


def read():
    with open(PS1, encoding="utf-8-sig") as f:
        return f.read()


class TestStart1024(unittest.TestCase):
    def test_default_strategy_is_validated_candidate(self):
        s = read()
        self.assertIn('[string]$Strategy = "speedc151"', s)
        self.assertNotIn("speedc068lo0", s)

    def test_start_time_is_parameterized(self):
        s = read()
        self.assertIn("[datetime]$StartAt", s)
        self.assertIn("$target = $StartAt", s)
        self.assertNotIn("$target = [datetime]'2026-09-17T19:45:00'", s)

    def test_token_and_server_are_explicitly_passed(self):
        s = read()
        line = [x for x in s.splitlines() if "_official_keepalive.py" in x]
        self.assertTrue(line, "必须调用 _official_keepalive.py")
        self.assertIn("--token-file $TokenFile", line[0])
        self.assertIn("--server $Server", line[0])

    @unittest.skipUnless(shutil.which("powershell") or shutil.which("pwsh"),
                         "需要 PowerShell 才能做语法解析")
    def test_powershell_parses(self):
        exe = shutil.which("powershell") or shutil.which("pwsh")
        code = ("$e=$null;$t=$null;"
                "[System.Management.Automation.Language.Parser]::ParseFile("
                "'%s',[ref]$t,[ref]$e)|Out-Null;"
                "if($e.Count){$e|%%{$_.Message};exit 1}else{exit 0}" % PS1.replace("'", "''"))
        p = subprocess.run([exe, "-NoProfile", "-Command", code],
                           capture_output=True, text=True, timeout=90)
        self.assertEqual(p.returncode, 0, "PowerShell 语法解析失败：%s" % (p.stdout + p.stderr)[:400])


if __name__ == "__main__":
    unittest.main()
