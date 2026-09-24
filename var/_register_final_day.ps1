# 注册 10/7 最终换臂 + 10/7/10/8 最终就绪校验（用户指令：10/7 换上最屌的模型，准备最后的比赛）。
#
# 三个一次性任务：
#   ① HangzhouMajFinalSwitch  @ 2026-10-07 09:00 → var/_switch_final.py --go   （读 .final_arm.txt；未选定就拒绝）
#   ② HangzhouMajFinalCheck   @ 2026-10-07 10:30 → var/_final_ready_check.py    （换完 1.5 小时后验收）
#   ③ HangzhouMajFinalCheck2  @ 2026-10-08 09:00 → var/_final_ready_check.py    （提交截止 12:00 前最后验收）
#
# 为什么用 pythonw：无控制台，不会被误关窗口/Ctrl+C 打死（R1393 教训）。日志见各自 var/_*.log/.out。
param([switch]$Go)
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
function Reg-One($name, $at, $script) {
  $args = '-X utf8 "{0}\var\{1}" --go' -f $root, $script
  if ($script -eq "_final_ready_check.py") { $args = '-X utf8 "{0}\var\{1}"' -f $root, $script }
  Write-Host "注册 $name @ $at → $pyw $args"
  if ($Go) {
    $action  = New-ScheduledTaskAction -Execute $pyw -Argument $args -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($at, "yyyy-MM-dd HH:mm:ss", $null))
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Get-ScheduledTaskInfo -TaskName $name | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
  }
}
Reg-One "HangzhouMajFinalSwitch"  "2026-10-07 09:00:00" "_switch_final.py"
Reg-One "HangzhouMajFinalCheck"   "2026-10-07 10:30:00" "_final_ready_check.py"
Reg-One "HangzhouMajFinalCheck2"  "2026-10-08 09:00:00" "_final_ready_check.py"
Write-Host "（加 -Go 才真正注册）"