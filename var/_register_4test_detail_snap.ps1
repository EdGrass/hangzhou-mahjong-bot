# 注册 `HangzhouMaj4TestDetailSnap`：四测期间每 10 分钟把**赛事详情**（ranking 全榜 / my_games / stage / qualified）
# 快照一行到 `var/4test_detail.jsonl`（只在签名变化时追加）。
#
# 为什么：2026-09-24 实测 —— 三测 `GET /api/tournaments/t_069a55e84b26` 现在 **404**、门户列表里也没了，
#   但单场复盘 `GET /portal/api/games/t_069a55e84b26_s2_b20_t0/events` 仍 **200**。
#   ⇒ **对局留得住、赛事视角留不住**：`ranking` 全榜和 `my_games`（赛后补拉复盘要用的 gid 清单）
#   过期即失。而 `_format_fidelity` 只留 status/stage/qualified/my_games **计数**，不留全榜。
#
# 红线：只发 1 个 GET + 追加一行 JSON；不杀进程、不改 bot/、不碰在途 A/B / official keepalive。
param(
  [switch]$Go,
  [int]$EveryMinutes = 10,
  [string]$At = "2026-09-24 15:00:00",
  [int]$DurationHours = 4,
  [int]$DurationMinutes = 45,
  [string]$Tid = "t_6266386bfd56",
  [string]$TokenFile = "D:\hangzhouMaj\var\.token_4test_20260924",
  [string]$TaskName = "HangzhouMaj4TestDetailSnap"
)
$root = "D:\hangzhouMaj"
$py   = (Get-Command python.exe).Source
$cmdArgs = '/c cd /d "{0}" && "{1}" -X utf8 var/_4test_watch_detail.py --tid {2} --token-file "{3}" >> "{0}\var\_4test_detail.out" 2>&1' -f $root, $py, $Tid, $TokenFile
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