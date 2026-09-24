# 注册 `HangzhouMajAdoptPairWatch`：每 10 分钟调用 `var/_adopt_pair.py --go`（**役 3 的双候选采用裁决 + 自动起役 4**）。
#
# 为什么需要它（本机核实的真缺口，R1439）：
#   `var/_bsegment.py` 起役时**只注册判词看护**（役 3 = `HangzhouMajVerdictWatch3bc/3v`），**不注册采用看护**；
#   而现成的 `HangzhouMajAdoptWatch` 只盯 `--label 役2`（已核）。
#   ⇒ 役 3 判词落地后**没有任何东西会起役 4**，整条链**静默停摆**；役 3 判词约 2.5 天后落地，
#     停一天就吃掉 10/7 前的余量。
#
# 它做什么：读两个候选的判词（`_verdict_役3bc.txt` / `_verdict_役3v.txt`）→ 对每个 ADOPT 跑**强手房否决**
#   （§7/§8 两层，阈值 z ≤ −2.0）→ 按役 3 读卡 §3 的**四格表**决定役 4 的基线/候选 → 调既有 `_bsegment.py --go`。
#   —— 判词没齐 / 读数异常 ⇒ **原地不动**；已裁决过 ⇒ 幂等 no-op。
#
# 为什么用 pythonw：无控制台，不会被误关窗口/Ctrl+C 打死（R1393 教训）。日志见 `var/_adopt_pair.log`。
#
# 红线：脚本自身不杀进程、不改 bot/；真正干活只走既有 B 段（它自己停驱动→等空档→P0→preflight→切役→注册看护）。
param(
  [switch]$Go,
  [int]$EveryMinutes = 10,
  [string]$TaskName = "HangzhouMajAdoptPairWatch",
  [string]$Label = "役3",
  [string]$Baseline = "speedvalue"
)
$root = "D:\hangzhouMaj"
$pyw  = Join-Path (Split-Path (Get-Command pythonw.exe).Source -Parent) "pythonw.exe"
$cmdArgs = '-X utf8 "{0}\var\_adopt_pair.py" --go --label {1} --baseline {2}' -f $root, $Label, $Baseline
Write-Host "任务名: $TaskName"
Write-Host "触发器: 每 $EveryMinutes 分钟（长期；裁决后脚本自身毫秒级 no-op）"
Write-Host "动作  : $pyw $cmdArgs"
Write-Host "  ★ --since 不传：脚本每次读 .ab_mode.started（= 本役起点），避免写死过期时间戳"
if ($Go) {
  $action  = New-ScheduledTaskAction -Execute $pyw -Argument $cmdArgs -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 70) -StartWhenAvailable
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,NextRunTime,LastTaskResult | Format-List
} else { Write-Host "（dry-run：未注册；加 -Go 才注册）" }
