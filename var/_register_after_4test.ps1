# 注册四测**收尾重试**（一次性×N）：到点跑 `var/_after_4test.py`
#   → 它会：若官方模式仍在，试退出（比赛在跑会被拒）；退出成功后用**原窗口**恢复役 2 A/B。
param([switch]$Go, [string]$At = "2026-09-24 19:00:00", [string]$TaskName = "HangzhouMajAfter4Test")
$root = 'D:\hangzhouMaj'
$py   = 'C:\Users\caiyuxin05\AppData\Local\Programs\Python\Python312\python.exe'
$args = '/c cd /d "{0}" && "{1}" -X utf8 var/_after_4test.py >> "{0}\var\_4test_after.out" 2>&1' -f $root, $py
Write-Host "任务名: $TaskName"
Write-Host "触发器: 一次性 @ $At"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null))
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
