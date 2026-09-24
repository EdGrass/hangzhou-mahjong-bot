# -*- coding: utf-8 -*-
# `var/_register_campaign3_watches.ps1` —— 役 3（三臂役）**两对判决看护**的计划任务注册器。
#
# 为什么：役 3 是**三臂役**（speedvalue 共享基线 + speedvaluebc + speedvaluebaotouv5），
# 判词要按**两对**分别落盘（同一 since）。手敲两条 schtasks 容易漏/写错 since
# ⇒ 本脚本把这步固化；**默认只打印命令**，加 `-Go` 才真的注册。
#
# 用法：
#   powershell -File var/_register_campaign3_watches.ps1 -Since "2026-09-25 03:00:00"        # 只看
#   powershell -File var/_register_campaign3_watches.ps1 -Since "2026-09-25 03:00:00" -Go    # 真注册
#
# 注意：`-Since` 必须与 `_switch_campaign --go` 打印的"起役时间戳"**完全一致**，
#       否则两对读的房集合会不一致（共享基线也会错位）。

param(
  [Parameter(Mandatory=$true)][string]$Since,
  [switch]$Go,
  [string]$Baseline = "speedvalue",
  [int]$IntervalMinutes = 10
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pyc = Get-Command pythonw.exe -ErrorAction SilentlyContinue
$py  = if ($pyc) { $pyc.Source } else { "C:\Users\caiyuxin05\AppData\Local\Programs\Python\Python312\pythonw.exe" }
$watch = Join-Path $root "var\_verdict_watch.py"

$pairs = @(
  @{ name = "HangzhouMajVerdictWatch3bc"; label = "役3bc"; cand = "speedvaluebc";         mech = "none" },
  @{ name = "HangzhouMajVerdictWatch3v";  label = "役3v";  cand = "speedvaluebaotouv5";   mech = "none" }
)

foreach ($p in $pairs) {
  $args = '-X utf8 "{0}" --label {1} --since "{2}" --baseline {3} --candidate {4} --mechanism {5}' -f `
          $watch, $p.label, $Since, $Baseline, $p.cand, $p.mech
  Write-Host "=== $($p.name) ==="
  Write-Host "  Execute  : $py"
  Write-Host "  Arguments: $args"
  Write-Host "  间隔 ${IntervalMinutes} 分钟；MultipleInstances=IgnoreNew；ExecutionTimeLimit=PT25M"
  if ($Go) {
    $action  = New-ScheduledTaskAction -Execute $py -Argument $args -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 25) -StartWhenAvailable
    Register-ScheduledTask -TaskName $p.name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "  → 已注册/更新"
  } else {
    Write-Host "  （dry-run：未注册；加 -Go 才真的注册）"
  }
}
