# 注册 `HangzhouMajLadderSnapshot`：每 30 分钟把门户榜单快照追加到 var/ladder_history.jsonl
# 为什么：`ladder_history.jsonl` 上一次记录是 09-23 22:04（~10 小时前）⇒ 趋势行是陈旧的，
#        而 10/7 的收尾判定会看"最近一段房的分/房"（`--show` 的趋势行）。
# 只读网络 + 追加一行 JSON；不影响任何对局进程。
param([switch]$Go, [int]$EveryMinutes = 30)
$root = "D:\hangzhouMaj"
$py   = (Get-Command python.exe).Source
$args = '/c cd /d "{0}" && "{1}" -X utf8 tools/ladder_snapshot.py --periods all >> "{0}\var\_ladder_snapshot.log" 2>&1' -f $root, $py
Write-Host "任务名: HangzhouMajLadderSnapshot"
Write-Host "触发器: 每 $EveryMinutes 分钟"
Write-Host "动作  : cmd.exe $args"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
  Register-ScheduledTask -TaskName "HangzhouMajLadderSnapshot" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName "HangzhouMajLadderSnapshot" | Select-Object NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
