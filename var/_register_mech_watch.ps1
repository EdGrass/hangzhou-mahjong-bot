# 注册 `HangzhouMajMechWatch`：役中机制端点守护（每 6 小时一次，读 .ab_mode 自动判当前役）。
#
# 为什么：`prereg-campaign3-speedvaluebc-20260924.md` 把「决策改动率 ∈ [10%,20%] 且 action 差异=0」定为该役**核心机制端点**，
#   并要求"每 20 房复跑一次 offline_replay"——人工数房必漏。本任务把它变成时间驱动的定期重抽。
# 行为：无 `.ab_mode`（没役在跑）⇒ 严格 no-op；有役 ⇒ 对候选臂跑 `offline_replay --lowprio`，
#   把读数写 `var/_mech_watch.log`；脱离预期带写 `var/.mech_warn`，正常则删除该标记。
# 为什么 pythonw：无控制台，不会被误关窗口/Ctrl+C 打死（R1393 教训）。
param([switch]$Go, [int]$EveryHours = 6, [string]$TaskName = "HangzhouMajMechWatch")
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
$args = '-X utf8 "{0}\var\_mech_watch.py" --files 200' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发器: 每 $EveryHours 小时（长期；无役时毫秒级 no-op）"
Write-Host "动作  : $pyw $args"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $args -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(30) -RepetitionInterval (New-TimeSpan -Hours $EveryHours)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }