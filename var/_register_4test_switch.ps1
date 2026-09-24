# 注册四测的**定时切换**（一次性）。
# ★ 为什么用 **系统 PowerShell 5.1 的绝对路径**：本机**没有系统 PowerShell 7**，
#   PATH 里的 `pwsh` 只有 Codex 自带的缓存副本（计划任务的 PATH 不一定看得到）；
#   而 5.1 在固定系统路径上，且我们今天已把全部 .ps1 补了 UTF-8 BOM
#   ⇒ 5.1 下解析 0 错、且 `-DryRun` 实跑通过。
param(
  [switch]$Go,
  [string]$At = "2026-09-24 15:20:00",
  [string]$TaskName = "HangzhouMaj4TestSwitch",
  [string]$Strategy = "speedvalue",
  [string]$TokenFile = "var/.token_4test_20260924",
  [string]$TournamentId = "t_6266386bfd56"
)
$root = 'D:\hangzhouMaj'
$ps   = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$args = '/c cd /d "{0}" && "{4}" -NoProfile -File var/_switch_to_official.ps1 -Strategy {1} -TokenFile {2} -TournamentId {3} -AllowNotReady >> "{0}\var\_4test_switch.out" 2>&1' -f $root, $Strategy, $TokenFile, $TournamentId, $ps
Write-Host "任务名: $TaskName"
Write-Host "触发器: 一次性 @ $At"
Write-Host "动作  : cmd.exe $args"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args
  $trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact($At, "yyyy-MM-dd HH:mm:ss", $null))
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
