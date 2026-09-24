# -*- coding: utf-8 -*-
# `var/_register_tminus_ready.ps1` —— **把 T-2min 的"分桌实到确认"任务指向正式赛**。
#
# 为什么必须显式重注册（本轮实测）：现役 `HangzhouMajTminusReady` 的动作**写死了三测的 tid/令牌**
#   （`--tid t_069a55e84b26 --token-file var\.token_3test_20260923`），
#   且触发器是**一次性**的 `StartBoundary 2026-09-23T19:58:30`（Repetition 为空）
#   ⇒ 它**已经跑完、永不再触发**。若 10/7 直接依赖它 ⇒ "分桌实到"确认**静默不发生**
#   （指南 §2.6：漏做会被剔出分桌）。
#
# 用法（默认只打印，`-Go` 才真注册）：
#   pwsh -NoProfile -File var/_register_tminus_ready.ps1 -Tid t_xxxx -TokenFile var/.token_<赛事>_<日期> -At "2026-10-07 19:58:00"
#   …再加 -Go
#
# 说明：`-At` 建议 = **开赛前 2 分钟**（与三测同样式）。脚本只做只读状态确认（`_ready_1024.py`），
#       §V.28 的手工三命令**仍是主路径**，本任务只是"别忘了/自动补一发"的保险。

param(
  [Parameter(Mandatory=$true)][string]$Tid,
  [Parameter(Mandatory=$true)][string]$TokenFile,
  [Parameter(Mandatory=$true)][string]$At,
  [string]$TaskName = "HangzhouMajTminusReady",
  [switch]$Go
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py   = Join-Path $root ".venv-does-not-exist"     # 占位，下面自动探测
$pyc  = Get-Command python.exe -ErrorAction SilentlyContinue
$py   = if ($pyc) { $pyc.Source } else { "C:\Users\caiyuxin05\AppData\Local\Programs\Python\Python312\python.exe" }

if ($Tid -notmatch '^t_[0-9a-f]+$') { throw "tid 形态可疑：$Tid（应为 t_<hex>）" }
$tokPath = if ([IO.Path]::IsPathRooted($TokenFile)) { $TokenFile } else { Join-Path $root $TokenFile }
if (-not (Test-Path $tokPath)) { throw "令牌文件不存在：$tokPath" }
$tok = (Get-Content -Raw -LiteralPath $tokPath).Trim()
if ($tok.Length -ne 64) { throw "令牌长度不是 64：$tokPath" }

$log = Join-Path $root "var\_tminus_ready.log"
$args = '/c cd /d "{0}" && "{1}" -X utf8 var\_ready_1024.py --tid {2} --token-file "{3}" >> "{4}" 2>&1' -f `
        $root, $py, $Tid, $tokPath, $log

Write-Host "=== $TaskName ==="
Write-Host "  触发器: 一次性 @ $At"
Write-Host "  动作  : cmd.exe $args"
Write-Host "  令牌  : $tokPath（64 位 ✓）"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]$At)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  $i = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host "  → 已注册；NextRunTime = $($i.NextRunTime)"
} else {
  Write-Host "  （dry-run：未注册；加 -Go 才真的注册）"
}
