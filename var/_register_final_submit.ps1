# 注册 HangzhouMajFinalSubmit：10/8 10:00 自动提交（_prepare_submission -Go + commit + push）。
#
# 为什么需要它：10/8 12:00 是**硬截止**，而"提交"原先完全靠人工（操作卡的最后一步）。
#   本机已验证 git push --dry-run 在非交互（GIT_TERMINAL_PROMPT=0）下成功 ⇒ 推送不需要人到场。
#   错过截止 = 没交上，所以这一步值得自动化，并把门禁写死（见 var/_submit_final.py 的 docstring）。
#
# 门禁（fail-closed）：_prepare_submission.ps1（只检查）rc 必须为 0 —— 它内部已覆盖交付物、4 个模型文件、
#   69 个运行期脚本、泄密门（无 64 位令牌串）、文案与代码版本一致；提交后还要校验"工作区干净 且 本地==origin/main"。
#   任一条不过 ⇒ 不提交、不推送、写 _submit_final.out 供人看（不会静默）。
#
# 为什么 pythonw：无控制台，不会被误关窗口/Ctrl+C 打死（R1393 教训）。日志 var/_submit_final.log。
param(
  [switch]$Go,
  [string]$At = "2026-10-08 10:00:00",
  [string]$TaskName = "HangzhouMajFinalSubmit"
)
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
$cmdArgs = '-X utf8 "{0}\var\_submit_final.py" --go' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发  : $At（截止 10/8 12:00 前 2 小时）"
Write-Host "动作  : $pyw $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $cmdArgs -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null))
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
