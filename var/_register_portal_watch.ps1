# 注册 `HangzhouMajPortalWatch`：每 30 分钟把门户赛事/公告快照追加到 var/_portal_history.jsonl
# 为什么：四测（t_6266386bfd56）是“偶然查门户”才发现的（当时距报名截止只剩 ~5h）；
#         10/10 正式赛的 tid 一旦上线也要尽早看到。本任务**只读**（GET 门户接口）+ 追加一行 JSON。
param([switch]$Go, [int]$EveryMinutes = 30)
$root = "D:\hangzhouMaj"
$py   = (Get-Command python.exe).Source
$args = '/c cd /d "{0}" && "{1}" -X utf8 var/_portal_watch.py >> "{0}\var\_portal_watch.log" 2>&1' -f $root, $py
Write-Host "任务名: HangzhouMajPortalWatch"
Write-Host "触发器: 每 $EveryMinutes 分钟"
Write-Host "动作  : cmd.exe $args"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
  Register-ScheduledTask -TaskName "HangzhouMajPortalWatch" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName "HangzhouMajPortalWatch" | Select-Object NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
