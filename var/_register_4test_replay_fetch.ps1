# 注册 `HangzhouMaj4TestReplayFetch`：四测赛后**自动补拉官方（门户格式）复盘**，每 30 分钟一次、幂等重试。
#
# 为什么需要：keepalive 跑四测时自己录的是 `var/replays/official_1024_<stamp>/<gid>.jsonl`（**裸事件流**），
#   而赛后审计/同席对比读的是**门户格式**（`<gid>.json`，含 seats/blocks）——
#   `tools/fetch_tournament_replays.py` 是那座桥，但它**只能在赛后手动跑**，
#   而门户**只保留当前 1 场赛事**（历史上多届因此查不到）⇒ 不自动化就是“证据一次性”。
#   该工具本身幂等（已存在的 `<gid>.json` 直接 skip），所以“每 30 分钟重试一遍”既安全又能吃掉
#   赛程尾部才落库的对局；`--dry-run` 实测（2026-09-24 14:5x，赛前）GET 200 / my_games=0，链路通。
#
# 红线：只发门户/API GET、只写 `var/replays/4test_rooms/` 与 `var/_4test_replayfetch.out`；
#       不杀进程、不改 bot/、不碰在途 A/B（与 19:00 的 `_after_4test.py` 恢复动作互不干扰）。
param(
  [switch]$Go,
  [string]$At = "2026-09-24 19:10:00",
  [int]$EveryMinutes = 30,
  [int]$DurationHours = 5,
  [int]$DurationMinutes = 0,
  [string]$Tid = "t_6266386bfd56",
  [string]$TokenFile = "D:\hangzhouMaj\var\.token_4test_20260924",
  [string]$OutDir = "var/replays/4test_rooms",
  [string]$TaskName = "HangzhouMaj4TestReplayFetch"
)
$root = "D:\hangzhouMaj"
$py   = (Get-Command python.exe).Source
$cmdArgs = '/c cd /d "{0}" && "{1}" -X utf8 tools/fetch_tournament_replays.py --tid {2} --token-file "{3}" --out {4} >> "{0}\var\_4test_replayfetch.out" 2>&1' -f $root, $py, $Tid, $TokenFile, $OutDir
Write-Host "任务名: $TaskName"
Write-Host "触发器: 从 $At 起每 $EveryMinutes 分钟，持续 $DurationHours 小时 $DurationMinutes 分钟"
Write-Host "动作  : cmd.exe $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdArgs
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null)) `
               -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
               -RepetitionDuration (New-TimeSpan -Hours $DurationHours -Minutes $DurationMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }