# `var/_final_switch_retry.ps1` —— 10/7 12:00 的**换臂重试**。
#
# 为什么要有它：10/7 08:30 的 `_final_arm_confirm.py` 只按当时的判词落盘。若役 5 的判词
#   在 09:00 换臂之后才落地，09:00 那次就只能装基线 —— 正式赛就会少叠一层已判正的层。
#   本脚本把"重算 → 若出现更深的已判正层就补装"补上。
#
# 安全口径（全部由被调脚本自己保证，本脚本不额外放宽）：
#   · `_final_arm_confirm.py --go --refresh`：只升级**本脚本自己写过**的臂；
#     人工写的裁决一律尊重、绝不降级、绝不越级到未判正的臂；
#   · `_switch_final.py --go`：官方模式在位/臂未选定/臂不可实例化 ⇒ 一律拒绝；
#     对"臂变了"是幂等的（重新停 A/B → 等对局自然结束 → 换臂）。
# 红线：不杀进程、不强停对局（等待超时也只是退出并记日志）。
param([string]$Root = "D:\hangzhouMaj", [switch]$DryRun)
$ErrorActionPreference = "Continue"
Set-Location $Root
$log = Join-Path $Root "var\_final_switch_retry.log"
function Write-Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -LiteralPath $log -Encoding UTF8 }
$py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "python" }
# -DryRun：排练档 —— 两条都只走 --dry-run（不碰 A/B、不换臂、不改任何状态）。
#   所以本包装脚本可以随时做**活体验收**，不必等 10/7。
$confirmArgs = @("var\_final_arm_confirm.py", "--go", "--refresh")
$switchArgs  = @("var\_switch_final.py", "--go")
if ($DryRun) {
  $confirmArgs = @("var\_final_arm_confirm.py", "--dry-run")
  $switchArgs  = @("var\_switch_final.py", "--dry-run")
}
Write-Log "=== 换臂重试开始（py=$py）==="
try {
  $a = & $py -X utf8 @confirmArgs 2>&1
  Write-Log "confirm rc=$LASTEXITCODE"
  $a | Add-Content -LiteralPath $log -Encoding UTF8
} catch { Write-Log "confirm 异常：$($_.Exception.Message)" }
try {
  $b = & $py -X utf8 @switchArgs 2>&1
  Write-Log "switch rc=$LASTEXITCODE"
  $b | Add-Content -LiteralPath $log -Encoding UTF8
} catch { Write-Log "switch 异常：$($_.Exception.Message)" }
Write-Log "=== 换臂重试结束 ==="
