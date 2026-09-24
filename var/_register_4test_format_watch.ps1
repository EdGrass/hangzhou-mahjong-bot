# 注册 `HangzhouMaj4TestFormatWatch`：四测期间每 10 分钟跑一次“赛制保真核对”，
# 把 config / stage / stage_status / qualified / my_games 的**变化**追加到 var/format_history.jsonl。
#
# 为什么需要：§V.153 的四条观察信号（stage 是否出现 / qualified 是否置位 / stage_done→stage_open
#   是否要重新 ready / 被淘汰者是否停打）**只在四测进行中存在**——门户只保留当前 1 场赛事，
#   事后再查必丢。R1386 已经把这些信号写进 `_format_fidelity` 的留档里，但**没有任何定时器在跑它**
#   ⇒ 不注册这个任务，观察清单就是“有工具、无证据”。
#
# 红线：只发门户 GET + 追加一行 JSON；不杀进程、不改 bot/、不碰在途 A/B、不影响 official keepalive。
param(
  [switch]$Go,
  [int]$EveryMinutes = 10,
  [string]$At = "2026-09-24 15:00:00",
  [int]$DurationHours = 4,
  [int]$DurationMinutes = 45,
  [string]$Tid = "t_6266386bfd56",
  [string]$TokenFile = "D:\hangzhouMaj\var\.token_4test_20260924",
  [string]$TaskName = "HangzhouMaj4TestFormatWatch"
)
$root = "D:\hangzhouMaj"
$py   = (Get-Command python.exe).Source
$cmdArgs = '/c cd /d "{0}" && "{1}" -X utf8 var/_format_fidelity.py --tid {2} --token-file "{3}" >> "{0}\var\_4test_format.out" 2>&1' -f $root, $py, $Tid, $TokenFile
Write-Host "任务名: $TaskName"
Write-Host "触发器: 从 $At 起每 $EveryMinutes 分钟，持续 $DurationHours 小时 $DurationMinutes 分钟"
Write-Host "动作  : cmd.exe $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdArgs
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null)) `
               -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
               -RepetitionDuration (New-TimeSpan -Hours $DurationHours -Minutes $DurationMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }