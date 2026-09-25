# 注册 HangzhouMajNextYakuNotice：每 10 分钟检查“役 4 判词是否已落地、下一步该怎么走”（只读）。
#
# 为什么：链上只有 `AdoptWatch`（役 2）与 `AdoptPairWatch`（役 3→役 4）两个自动推进器；
#   **役 4 判词落地后没有任何计划任务去消费它** ⇒ 默认会“继续跑役 4 超过役盒（白烧房位）+
#   役 5（三层组合臂）永远不起”。
#   而 §V.186 对候选臂剂量口径留了一个**未定选择**（`speedvaluebcvmeld` 还是 `...p40`）⇒
#   不能自动写死。本任务只把“该决定了 + 可照拄命令”落到 `var\.YAKU_NEXT_PENDING`。
#
# 只读：不碰进程、不改 `.ab_mode`、不自己起役。为什么 pythonw：无控制台、不会被误关。
param(
  [switch]$Go,
  [int]$EveryMinutes = 10,
  [string]$TaskName = "HangzhouMajNextYakuNotice"
)
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
$cmdArgs = '-X utf8 "{0}\var\_next_yaku_notice.py" --label 役4' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发  : 每 $EveryMinutes 分钟（首次 1 分钟后）"
Write-Host "动作  : $pyw $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $cmdArgs -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
