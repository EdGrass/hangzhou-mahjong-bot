# 注册 10/10 正式赛的**两个一次性任务**（把上线步骤里的人工降到"只放一个令牌文件"）：
#   ① HangzhouMajFinalEventSwitch @ 2026-10-10 18:50
#       → var/_final_event_switch.py --go
#       （读 .final_arm.txt 的臂 + var/.token_final_20261010 的令牌 → 门户解析唯一 registering 赛事 tid
#         → 调现成 _switch_to_official.ps1，不带 -AllowNotReady）
#   ② HangzhouMajFinalEventReady  @ 2026-10-10 19:25（★R1452 改为开关感知：不在官方模式就先重试上线）
#       → var/_ready_1024.py --token-file var/.token_final_20261010
#       （tid 由 .official_spec.json/门户自解析；幂等；T-5 保险）
# 为什么用 pythonw：无控制台，不会被误关窗口/Ctrl+C 打死（R1393 教训）。
# 红线：不传 -AllowNotReady；缺令牌/缺最终臂/解析不到 tid 一律拒绝并记日志。
param(
  [switch]$Go,
  [string]$SwitchAt = "2026-10-10 18:50:00",
  [string]$ReadyAt  = "2026-10-10 19:25:00",
  [string]$TokenFile = "D:\hangzhouMaj\var\.token_final_20261010"
)
$root = "D:\hangzhouMaj"
$pyw  = (Get-Command pythonw.exe).Source
function Reg-One($name, $at, $argStr) {
  Write-Host "注册 $name @ $at → $pyw $argStr"
  if ($Go) {
    $action  = New-ScheduledTaskAction -Execute $pyw -Argument $argStr -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($at, "yyyy-MM-dd HH:mm:ss", $null))
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Get-ScheduledTaskInfo -TaskName $name | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
  }
}
Reg-One "HangzhouMajFinalEventSwitch" $SwitchAt ('-X utf8 "{0}\var\_final_event_switch.py" --go' -f $root)
# ★ R1452：19:25 改为「开关感知」的 T-5 保险：
#   若 .official_mode 已在位 ⇒ 行为与原来完全一致（只补 ready）；
#   若不在位 ⇒ 先**重试上线**（同一套 fail-closed，仍不传 -AllowNotReady），再补 ready；
#   仍不在位 ⇒ 落 var/.EVENT_SWITCH_BLOCKED（含可照抄的人工命令 + 逃生阀写法）—— 原来这里没有第二次机会。
Reg-One "HangzhouMajFinalEventReady"  $ReadyAt  ('-X utf8 "{0}\var\_final_event_ready.py"' -f $root)
Write-Host "（加 -Go 才真正注册）"