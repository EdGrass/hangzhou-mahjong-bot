# -*- coding: utf-8 -*-
"""`var/_switch_to_official.ps1`（开赛切换脚本）的**接线单测**。

为什么要单测一个 .ps1（只读文本 + 可选语法解析）：
2026-09-17 发现 `_ready_1024.py` / `tools/rules_guard.py` 都把**赛事 id / 令牌文件**写成默认值，
而切换脚本调它们时**不传参** ⇒ 对"一个月后的正式赛"（换赛事、换令牌）会：
  ① POST /ready 打到**旧赛事**（正式赛那一场反而没到位 ⇒ 开赛被剔出分桌）；
  ② rules_guard 查的是**旧赛事**的 YouCaiBiKao（策略闸门判断错 ⇒ 有白平胡会被 409 拒）。
这与 `_ensure_all.py` 不带参数那次是同一类事故，所以用单测把"参数必须贯通"钉住。

关键不变量：
  ① 脚本有 `-TournamentId` 参数，且 rules_guard / _ready_1024 都被显式传 `--token-file`；
  ② `_ready_1024.py` 还必须收到 `--tid`；
  ③ `.official_spec.json` 里要带 `tournament_id`（整机重启后自愈链要用）；
  ④ 步骤 3 必须同时等 **run_bot 与 _ab_driver** 退出（E002 防护）；
  ⑤ 有 `-DryRun` 且 dry-run 路径不写哨兵/不调 ready（可演练而不扰动线上）。
"""
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "var", "_switch_to_official.ps1")


def read():
    with open(PS1, encoding="utf-8-sig") as f:
        return f.read()


class TestSwitchWiring(unittest.TestCase):
    def test_tournament_id_param(self):
        s = read()
        self.assertIn("$TournamentId", s, "必须有可更换的赛事 id 参数")

    def test_rules_guard_gets_token(self):
        s = read()
        line = [x for x in s.splitlines() if "rules_guard.py" in x and "& python" in x]
        self.assertTrue(line, "必须调用 rules_guard.py")
        self.assertIn("--token-file $TokenFile", line[0],
                      "rules_guard 必须用本场令牌（否则查的是旧赛事规则）")

    def test_ready_gets_tid_and_token(self):
        s = read()
        line = [x for x in s.splitlines() if "_ready_1024.py" in x and "& python" in x]
        self.assertTrue(line, "必须调用 _ready_1024.py")
        self.assertIn("--tid $TournamentId", line[0], "/ready 必须打到本场赛事")
        self.assertIn("--token-file $TokenFile", line[0], "/ready 必须用本场令牌")

    def test_spec_has_tournament_id(self):
        s = read()
        self.assertIn("tournament_id = $TournamentId", s,
                      ".official_spec.json 必须带 tournament_id（自愈链重启要用）")

    def test_waits_for_ab_driver(self):
        s = read()
        self.assertIn("_ab_driver\\.py", s, "步骤 3 必须检测 A/B 驱动")
        self.assertRegex(s, r"if \(\$dr\)[\s\S]{0,200}exit 3",
                         "_ab_driver 仍在跑时必须非零退出（E002 防护）")

    @staticmethod
    def _dryrun_bodies(s):
        """取出所有 `if ($DryRun) { ... }` 的**分支体**（花括号配对扫描）。

        为什么不用正则钉 `步骤2b/5` 这类标签：R1338 把步骤重编号成 2b-1/2b-2（先写 spec 再写哨兵）后，
        旧正则仍盯 `步骤2b/5` ⇒ **测试变红而代码是对的**（脆测试，不是缺陷）。
        这里改成钉**语义**：dry-run 分支里不得出现任何写盘 / 起进程动作。
        """
        out, key = [], "if ($DryRun) {"
        i = s.find(key)
        while i != -1:
            j = i + len(key) - 1          # j 指向 "分支开始的 '{'"
            depth, k = 0, j
            while k < len(s):
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            out.append(s[j + 1:k])
            i = s.find(key, k)
        return out

    def test_dry_run_is_read_only(self):
        s = read()
        self.assertIn("[switch]$DryRun", s)
        bodies = self._dryrun_bodies(s)
        self.assertTrue(bodies, "必须存在 `if ($DryRun) { ... }` 分支（否则本测是空跑）")
        for b in bodies:
            for bad in ("Set-Content", "Add-Content", "Out-File", "WriteAllText",
                        "Start-Process", "Stop-Process", "_ready_1024.py"):
                self.assertNotIn(bad, b,
                                 "dry-run 分支里不得出现 %s（否则 -DryRun 会写线上文件 / 起真正赛进程）：%r"
                                 % (bad, b.strip()[:200]))
        # 两处真正的写盘必须落在 `} else {` 之后（即非 dry-run 分支）
        for needle in ("WriteAllText($specPath", "Set-Content -Path $flag"):
            k = s.find(needle)
            self.assertNotEqual(k, -1, "找不到写盘语句 %s" % needle)
            self.assertNotEqual(s.rfind("} else {", 0, k), -1,
                                "%s 必须在 `} else {` 之后（即被 DryRun 守卫）" % needle)
        # POST /ready 必须被 dry-run 分支挡住
        self.assertRegex(s, r"if \(-not \$DryRun\) \{\s*\n\s*\$rd = & python -X utf8 var/_ready_1024\.py")

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
