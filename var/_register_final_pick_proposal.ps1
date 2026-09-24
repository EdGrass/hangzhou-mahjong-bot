# 注册 `HangzhouMajFinalPickProposal`：**10/5 09:00 一次性**跑 `var/_final_pick_proposal.py`，
# 把"最终臂提案 + 依据（§V.66 序列）"落到 `var/_final_pick_proposal.txt`，供 10/7 换臂前确认。
# 为什么：10/7 的换臂依赖 `var/.final_arm.txt`（缺失则拒绝，宁可不动也不猜）；
#   而选臂依据是现成工具 `var/_pick_arm.py`。本任务把这一步提前算好，避免临场手忙。
# 红线：只读台账/榜单 + 只写自己的提案文件；不改 .ab_mode / _keeper_strategy.txt / 不碰进程。
param([switch]$Go, [string]$At = "2026-10-05 09:00:00", [string]$TaskName = "HangzhouMajFinalPickProposal")
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
$args = '-X utf8 "{0}\var\_final_pick_proposal.py"' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发器: 一次性 @ $At"
Write-Host "动作  : $pyw $args"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $args -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null))
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }