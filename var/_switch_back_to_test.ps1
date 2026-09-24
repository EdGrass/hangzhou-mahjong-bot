param(
  [string]$Strategy = "",
  [int]$WaitMinutes = 25,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
function Info($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

if (-not $Strategy) {
  $sf = Join-Path $root 'var/_keeper_strategy.txt'
  $Strategy = if (Test-Path $sf) { (Get-Content $sf -Raw).Trim() } else { 'speedc073w4' }
}
Info ("目标测试房策略: " + $Strategy)

$of = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match '_official_keepalive\.py' }
if ($of) {
  Info ("步骤1/4: 停正式赛 keepalive pid=" + ($of.ProcessId -join ','))
  if (-not $DryRun) { foreach ($p in $of) { Stop-Process -Id $p.ProcessId -ErrorAction SilentlyContinue } }
} else { Info "步骤1/4: 未发现正式赛 keepalive" }

Info "步骤2/4: 等待正式赛 run_bot 自然退出（绝不中途杀）"
$deadline = (Get-Date).AddMinutes($WaitMinutes)
while ((Get-Date) -lt $deadline) {
  $rb0 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'run_bot\.py' }
  if (-not $rb0) { break }
  if ($DryRun) { break }
  Start-Sleep -Seconds 20
}
$rb = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'run_bot\.py' }
if ($rb) {
  Info ("  仍有 run_bot=" + @($rb).Count + " 在跑 —— 请稍后重跑本脚本")
  if (-not $DryRun) { exit 2 }
}

Info "步骤3/4: 启动测试房 keeper"
if (-not $DryRun) {
  Set-Content -Path (Join-Path $root 'var\.keeper.lock') -Value '0' -NoNewline
  Start-Sleep -Seconds 3
}
if ($DryRun) {
  Info ("  [dry-run] python -X utf8 -u var/_keeper.py " + $Strategy + " 4")
} else {
  Start-Process -FilePath python -ArgumentList @('-X','utf8','-u','var/_keeper.py',$Strategy,'4') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'var\_keeper_console.out') -RedirectStandardError (Join-Path $root 'var\_keeper_console.err')
  Start-Sleep -Seconds 10
}

$k = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match '_keeper\.py' }
if ($DryRun) { Info "  [dry-run] 跳过" }
elseif ($k) { Info ("  测试房 keeper 已运行 pid=" + ($k.ProcessId -join ',')) }
else { Info "  ⚠ 未检测到 keeper，请查看 var/_keeper_console.err" }
