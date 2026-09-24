# 注册 `HangzhouMajAdoptWatch`：每 10 分钟调用 `var/_adopt_when_ready.py`（役 2 判词一见 ADOPT 就自动执行 B 段）。
#
# 为什么：用户 2026-09-24 授权「都做 + 你自己想办法」（§V.160）；役 2 判词预计 09-25 凌晨落地，
#   而每个役只剩约 2 天 ⇒ 不能等人到场才起役 3。
#
# 为什么用 pythonw（不是 cmd/powershell）：本机 15:20 那次切换任务被 Ctrl+C/关窗打死过一次（R1393），
#   pythonw + CREATE_NO_WINDOW 路径没有控制台，不会被误关；且脚本把结果写 `var/_adopt_when_ready.log`。
#
# 红线：脚本自身不杀进程、不改 bot/；只在「判词决定性且为 ADOPT」时调用既有 `_bsegment.py --go`。
param(
  [switch]$Go,
  [int]$EveryMinutes = 10,
  [string]$TaskName = "HangzhouMajAdoptWatch"
)
$root = "D:\hangzhouMaj"
$pyw  = Join-Path (Split-Path (Get-Command pythonw.exe).Source -Parent) "pythonw.exe"
$cmdArgs = '-X utf8 "{0}\var\_adopt_when_ready.py" --label 役2' -f $root
Write-Host "任务名: $TaskName"
Write-Host "触发器: 每 $EveryMinutes 分钟（长期；采用后脚本自身毫秒级 no-op）"
Write-Host "动作  : $pyw $cmdArgs"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $cmdArgs -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 70) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }