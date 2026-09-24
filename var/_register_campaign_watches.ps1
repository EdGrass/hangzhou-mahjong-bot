# `var/_register_campaign_watches.ps1` —— **通用**役次判决看护注册器（N 臂任意役）。
#
# 为什么：`_register_campaign3_watches.ps1` 把役 3 的两对（speedvaluebc / speedvaluebaotouv5）
#   写死在脚本里；役 4/役 5 的候选与基线都不一样，再手敲两条注册命令就容易写错
#   **since / 臂名 / mechanism**（R1156/R1341 都栽过"手抄参数不一致"）。
#   本脚本把"一个基线 + N 个候选"变成参数，**默认只打印**，加 `-Go` 才注册。
#
# 用法（役 4 例：基线 speedvaluebc，候选 speedvaluebcmeldp45，机制口径 none）
#   powershell -File var/_register_campaign_watches.ps1 -Label 役4 -Since "2026-09-29 03:00:00" `
#       -Baseline speedvaluebc -Candidates speedvaluebcmeldp45
#   ... 加 -Go 真注册（每个候选一个任务）
#
# 命名约定：任务名 = "$TaskNamePrefix`_$Label`_$Candidate"（sanitize：非字母数字→_）
param(
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$Since,
  [Parameter(Mandatory=$true)][string]$Baseline,
  [Parameter(Mandatory=$true)][string]$Candidates,
  [string]$Mechanism = "none",
  [int]$IntervalMinutes = 10,
  [string]$TaskNamePrefix = "HangzhouMajVerdictWatch",
  [switch]$Go
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pyc = Get-Command pythonw.exe -ErrorAction SilentlyContinue
$py  = if ($pyc) { $pyc.Source } else { "C:\Users\caiyuxin05\AppData\Local\Programs\Python\Python312\pythonw.exe" }
$watch = Join-Path $root "var\_verdict_watch.py"
foreach ($cand in ($Candidates -split "," | Where-Object { $_.Trim() })) {
  $c = $cand.Trim()
  # 只洗候选臂名（任务名用）；**Label 保留原样**（含中文也行，与 `役3bc` 命名一致）
  $safeCand = $c -replace '[^A-Za-z0-9_]', '_'
  $task = $TaskNamePrefix + "_" + $Label + "_" + $safeCand
  $verdictLabel = $Label + $safeCand
  $args = '-X utf8 "{0}" --label "{1}" --since "{2}" --baseline {3} --candidate {4} --mechanism {5}' -f `
          $watch, $verdictLabel, $Since, $Baseline, $c, $Mechanism
  Write-Host "=== $task ==="
  Write-Host "  Execute  : $py"
  Write-Host "  Arguments: $args"
  Write-Host "  间隔 ${IntervalMinutes} 分钟；MultipleInstances=IgnoreNew；ExecutionTimeLimit=PT25M"
  if ($Go) {
    $action  = New-ScheduledTaskAction -Execute $py -Argument $args -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 25) -StartWhenAvailable
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Get-ScheduledTaskInfo -TaskName $task | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
  }
}
if (-not $Go) { Write-Host "（dry-run：未注册；加 -Go 才注册）" }