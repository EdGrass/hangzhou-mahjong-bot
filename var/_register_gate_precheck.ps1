# 注册四测的“规则预检”（15:05 一次性）：读赛事 config 的 YouCaiBiKao，
# 并按结果把 3 个切换任务重注册成正确的臂（true ⇒ speedvalueycbk；false ⇒ speedvalue）。
param([switch]$Go, [string]$At = "2026-09-24 15:05:00", [string]$TaskName = "HangzhouMaj4TestGatePrecheck")
$root = 'D:\hangzhouMaj'
$py   = 'C:\Users\caiyuxin05\AppData\Local\Programs\Python\Python312\python.exe'
$args = '/c cd /d "{0}" && "{1}" -X utf8 var/_4test_gate_precheck.py >> "{0}\var\_4test_gate_precheck.out" 2>&1' -f $root, $py
Write-Host "任务名: $TaskName"
Write-Host "触发器: 一次性 @ $At"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null))
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
