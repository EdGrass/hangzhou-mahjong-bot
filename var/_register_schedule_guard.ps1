# 注册 HangzhouMajScheduleGuard：每天 09:00 / 21:00 跑排期护栏（只读，把"会不会赶不上 10/7"量出来）。
#
# 为什么：§V.66 的功率分析说多数役到 120 房/臂（役盒）仍不可判定，真正收口靠破平；而实测吞吐 3.34 房/小时，
#   "全到盒"投影 ≈ 10/06 17:30 vs 截止 10/07 08:30 ⇒ **只剩 ~15 小时余量**。
#   计划里已有丢弃顺序（§V.160：先丢 V 剂量档 → 再丢组合验证），但没有机械触发 ⇒ 本任务把读数与标记维持住：
#   投影晚于截止时写 var/.SCHEDULE_TIGHT（含建议丢哪一役），够则自动清掉。
#
# 只读：不碰进程、不改 .ab_mode、不自行丢役。为什么 pythonw：无控制台、不会被误关（R1393 教训）。
param(
  [switch]$Go,
  [int]$EveryHours = 12,
  [string]$TaskName = "HangzhouMajScheduleGuard"
)
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
$cmdArgs = '-X utf8 "{0}\var\_schedule_guard.py"' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发  : 每 $EveryHours 小时（首次 2 分钟后）"
Write-Host "动作  : $pyw $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $cmdArgs -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours $EveryHours)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
