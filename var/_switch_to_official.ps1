param(
  [string]$Strategy = "",
  [string]$TokenFile = "",
  # ★ 2026-09-17 新增：赛事 id 必须能换。此前 `_ready_1024.py` / 状态脚本把
  #   t_65d538e905c5（09-17 二测）写死在默认值里，而本脚本调它们**不传参** ⇒
  #   "一个月后的正式赛"换令牌/换赛事时，POST /ready 会打到**旧赛事**上，
  #   正式赛那一场反而没到位 ⇒ 开赛被剔出分桌（与 `_ensure_all.py` 不带参数那次同类）。
  [string]$TournamentId = "",
  [int]$WaitMinutes = 25,
  # ★ R1319：**应急逃生阀**。`tools/preflight.py` 只要见到"未知 BREAKING"就 NOT READY，
  #   而本脚本原本**直接 throw** ⇒ 若平台在比赛前上了 v36（哪怕只是无害变更），
  #   正式赛就会**开不起来**。现在：加 `-AllowNotReady`（或环境变量 HM_ALLOW_NOT_READY=1）
  #   可**显式、响亮地绕过这一道**（依然跑 rules_guard 等其他门禁）—— 人做决定，不静默。
  [switch]$AllowNotReady,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
function Info($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
function Get-PyProcs([string]$Pattern) {
  # 必须同时匹配 python.exe 与 pythonw.exe：keeper/watchdog/run_bot/match_super 实际都以
  # pythonw.exe 启动（2026-09-15 实测 4 个进程全是 pythonw.exe），只筛 python.exe 会全部漏报
  # —— 后果是本脚本以为「对局已结束 / 无残留」，带着测试房并发进正式赛（E002 同账号）。
  Get-CimInstance Win32_Process |
    Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match $Pattern }
}

# ★ 2026-09-24（R1271）：把"历史默认值"改成**显式必填**。
#   旧默认是 09-17 二测的 token/tid ⇒ 若有人不带参调用，POST /ready 会打到**已结束的赛事**上，
#   正式赛那场反而没到位（与 T-minus 任务写死三测同类事故）。宁可直接报错。
if (-not $TokenFile -or -not $TournamentId) {
  throw "必须显式传 -TokenFile 与 -TournamentId（禁止沿用历史默认值：旧值会把 POST /ready 打到已结束的赛事上）"
}

$script:StrategyFromFile = $false
if (-not $Strategy) {
  $sf = Join-Path $root 'var\_keeper_strategy.txt'
  $Strategy = if (Test-Path $sf) { (Get-Content $sf -Raw).Trim() } else { 'speedc073w4' }
  $script:StrategyFromFile = $true
}
$allowNR = $AllowNotReady -or ($env:HM_ALLOW_NOT_READY -match '^(1|true|yes)$')
if ($allowNR) {
  Info "⚠⚠ 已启用 -AllowNotReady：preflight 非 READY 时**不中止**（仅记录）—— 仅在明确知道风险时使用"
}
Info ("目标策略: " + $Strategy)
Info ("目标赛事: " + $TournamentId + "   令牌文件: " + $TokenFile)

# 1) 开赛前体检
Info "步骤1/5: preflight"
if (-not $DryRun) {
  $pfAll = & python -X utf8 tools/preflight.py 2>&1
  $pf = ($pfAll | Select-Object -Last 1)
  Info ("  " + $pf)
  if ($pf -notmatch 'READY') {
    $pfAll | Select-Object -Last 6 | ForEach-Object { Info ("      " + $_) }
    if ($allowNR) {
      Info "  ⚠ 已按 -AllowNotReady 继续（preflight 非 READY）—— 请确认上面 6 行的具体原因是可接受的"
    } else {
      throw "preflight 未 READY，终止（若已确认原因无害，可显式加 -AllowNotReady 重跑）"
    }
  }

}

# 1b) 规则一致性：YouCaiBiKao ↔ 策略（2026-09-16 新增）
#     指南 §1.6：YouCaiBiKao 每场可配；若 true 而我们跑无闸门策略 ⇒ 有白平胡（占我方胡牌 64.4%）会被 409 拒；
#     若 false 而跑 speedc148/153（含闸门）⇒ 会主动拒掉合法平胡。用退出码把这件事变成硬门禁。
Info "步骤1b/5: rules_guard（YouCaiBiKao ↔ 策略）"
if (-not $DryRun) {
  & python -X utf8 tools/rules_guard.py --strategy $Strategy --token-file $TokenFile
  $rc = $LASTEXITCODE
  if ($rc -eq 2) { throw ("rules_guard 判定『不一致』：策略 $Strategy 与本场 YouCaiBiKao 不匹配，终止。" +
      "★ 修法（R1332 已注册保险孪生）：若赛事 YouCaiBiKao=true 而我们跑的是**无闸门臂** ⇒ 改用带 **ycbk 后缀**的孪生臂；" +
      "反之若赛事=false 而跑的是**闸门臂** ⇒ 去掉 ycbk 后缀改回无闸门臂。" +
      "已注册：speedvalueycbk / speedgangtakefixedycbk / speedmeldmore0chiycbk / speedmeldtol2chiycbk。" +
      "定案前先重跑 rules_guard 确认 rc=0。") }
  if ($rc -eq 3) { Info "  ⚠ rules_guard 读不到 config（令牌/网络）⇒ 必须人工确认 YouCaiBiKao 后再开赛" }
  Info ("  rules_guard 退出码 = " + $rc)
} else {
  Info "  [dry-run] python -X utf8 tools/rules_guard.py --strategy $Strategy --token-file $TokenFile"
}

# 2) 停测试房守夜人（只停 supervisor，不杀对局）
$lock = Join-Path $root 'var\.keeper.lock'
if (Test-Path $lock) {
  $kpid = (Get-Content $lock -Raw).Trim()
  if ($kpid -match '^\d+$' -and [int]$kpid -gt 0) {
    Info ("步骤2/5: 停 keeper pid=" + $kpid)
    if (-not $DryRun) { Stop-Process -Id ([int]$kpid) -ErrorAction SilentlyContinue }
  }
}
if (-not $DryRun) { Set-Content -Path $lock -Value '0' -NoNewline }

# 2b-2) 把"本次官方赛用的策略/令牌/服务器"落盘（var\.official_spec.json）
#   为什么必须：整机重启后由 `_ensure_all.py`（计划任务，每 5 分钟）拉起 keepalive ——
#   修复前它**不带参数**，会回落默认（speedtugc + 二测令牌）⇒ 正式赛换令牌后等于**静默不参赛**。
if ($DryRun) {
  Info ("步骤2b-1/5: [dry-run] 将写 var\.official_spec.json: strategy=" + $Strategy + " token_file=" + $TokenFile + " tournament_id=" + $TournamentId)
} else {
  $specPath = Join-Path $root 'var\.official_spec.json'
  # ★ R1393：**必须带 `ts`**——`_official_guard.spec_freshness()` 以“spec 有无/是否超 12h 的 `ts`”为自愈前提，
  #   四测实罕：旧版本写出的 spec 无 `ts` ⇒ 哨兵已上、keepalive 未起的那段窗口里 60s 看护**拒绝自愈**（只剩 5 分钟兜底）。
  $specObj = @{ strategy = $Strategy; token_file = $TokenFile; tournament_id = $TournamentId;
                server = 'https://10.240.169.190:18080';
                ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') } | ConvertTo-Json -Compress
  # ★ R1344：**不能用 `Set-Content -Encoding UTF8`** —— Windows PowerShell 5.1 会写 **BOM**（EF BB BF），
  #   而下游全部按 JSON 解析它：带 BOM 会直接抛 `JSONDecodeError: Unexpected UTF-8 BOM`
  #   ⇒ `_ensure_all.official_argv()` 误判“spec 缺失”后回落**默认策略 + 默认令牌** 拉起 keepalive（即 R647 的静默风险）；
  #   ⇒ `_official_guard.spec_freshness()` 会因“解析失败”拒绝自愈。
  #   故显式用 .NET 写**无 BOM** UTF-8（与 `utf-8-sig` 读取方互为双重保险）。
  [System.IO.File]::WriteAllText($specPath, $specObj, (New-Object System.Text.UTF8Encoding($false)))
  Info ("步骤2b-1/5: 已写 var\.official_spec.json（自愈重启按它传参）")
}

# 2b) 官方赛哨兵：禁止 watchdog（每 90s）与计划任务（每 5min）把测试房 keeper 拉回来
$flag = Join-Path $root 'var\.official_mode'
if ($DryRun) {
  Info "步骤2b-2/5: [dry-run] 将写入官方赛哨兵 var\.official_mode（停用测试房自愈）"
} else {
  Set-Content -Path $flag -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
  if (-not (Test-Path $flag)) { throw "哨兵写入失败，终止：否则 90s 内 keeper 会被自愈拉回并与正式赛并发" }
  Info "步骤2b-2/5: 已开启官方赛模式（var\.official_mode）——测试房自愈已停用"
}


# 2c) 到位确认（POST /ready）——分桌实到 = ready 且开赛前 90s 内在线（有已认证请求）
#     全仓无任何代码提交 ready（报名不等于到位），漏了这一步开赛时会被剔出分桌
if (-not $DryRun) {
  $rd = & python -X utf8 var/_ready_1024.py --tid $TournamentId --token-file $TokenFile 2>&1
  Info ("步骤2c/5: " + (($rd | Out-String).Trim() -replace "\r?\n", " | "))
  if ($LASTEXITCODE -ne 0) { throw "到位确认（POST /ready）失败，终止" }
} else {
  Info ("步骤2c/5: [dry-run] 将执行 python -X utf8 var/_ready_1024.py --tid " + $TournamentId + " --token-file " + $TokenFile + "（POST /ready，幂等）")
}

# 3) 等当前对局结束（绝不中途杀 run_bot）；**并且等 A/B 驱动退出**
#    为什么必须等驱动：驱动在"检查官方赛哨兵"之后、排批之前有一个窗口 ⇒ 若它此刻排批，
#    就会与随后启动的正式赛 keepalive **同账号并发 = E002**（2026-09-16 补）。
Info "步骤3/5: 等待 run_bot 自然退出 + A/B 驱动退出（不中途杀）"
$deadline = (Get-Date).AddMinutes($WaitMinutes)
while ((Get-Date) -lt $deadline) {
  $rb = Get-PyProcs 'run_bot\.py'
  $ms = Get-PyProcs 'match_super\.py'
  $dr = Get-PyProcs '_ab_driver\.py'
  if (-not $rb -and -not $ms -and -not $dr) { break }
  if ($DryRun) { break }
  Start-Sleep -Seconds 20
}
$rb = Get-PyProcs 'run_bot\.py'
$ms = Get-PyProcs 'match_super\.py'
$dr = Get-PyProcs '_ab_driver\.py'
if ($rb -or $ms) {
  Info ("  仍有对局/监督进程：run_bot={0} match_super={1} —— 请等其自然结束后重跑本脚本" -f @($rb).Count, @($ms).Count)
  if (-not $DryRun) { exit 2 }
}
if ($dr) {
  Info ("  ⚠ _ab_driver 仍在跑（{0} 个）——它会看到官方赛哨兵后自行退出；若超过 {1} 分钟仍在，说明它卡在排批窗口，**必须人工确认后再起正式赛**（否则 E002）" -f @($dr).Count, $WaitMinutes)
  if (-not $DryRun) { exit 3 }
}

# 3b) ★ R1307 一致性断言：`_keeper_strategy.txt` 在 A/B 期间会被驱动**每批改写成"本批的臂"**，
#      而驱动退出时又会把**基线**写回。
#      若本脚本的 `$Strategy` 是"从文件读出来的"（未显式传 -Strategy），那么刚才读到的
#      很可能是**A/B 中的候选臂**，而等待期间文件已被改回基线 ⇒ 不声不响地带错臂参赛。
#      这里拿到**等待后**的真值做断言：不一致就停（fail-safe，宁可让人重跑）。
if ($script:StrategyFromFile -and (Test-Path $sf)) {
  $stratNow = (Get-Content $sf -Raw).Trim()
  if ($stratNow -and $stratNow -ne $Strategy) {
    if ($DryRun) {
      Info ("  [dry-run] ⚠ 策略文件与本脚本一致性断言：" + $Strategy + " vs " + $stratNow + "（真跑会在此处终止）")
    } else {
      throw ("策略不一致：本脚本开始时从文件读到 $Strategy，等待 A/B 退出后文件已是 $stratNow。" +
             "说明当时读到的是 A/B 候选臂。请**显式**传 -Strategy <最终要参赛的臂>（并确认它是已验证臂）后重跑本脚本。")
    }
  } elseif ($DryRun) {
    Info ("  [dry-run] ✓ 策略一致性断言已执行：" + $Strategy)
  }
}

# 4) 起正式赛 keepalive
Info "步骤4/5: 启动正式赛 keepalive"
$args = @('-X','utf8','var/_official_keepalive.py','--strategy',$Strategy,'--token-file',$TokenFile)
if ($DryRun) {
  Info ("  [dry-run] python " + ($args -join ' '))
} else {
  Start-Process -FilePath python -ArgumentList $args -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $root 'var\_official_console.out') `
    -RedirectStandardError  (Join-Path $root 'var\_official_console.err')
  Start-Sleep -Seconds 12
}

# 5) 校验
Info "步骤5/5: 校验进程"
$ok = Get-PyProcs '_official_keepalive\.py'
$residK = Get-PyProcs '_keeper\.py'
$residM = Get-PyProcs 'match_super\.py'
$residW = Get-PyProcs '_watchdog\.py'
$residA = Get-PyProcs '_ab_driver\.py'
if ($DryRun) { Info "  [dry-run] 跳过" }
else {
  if ($ok) { Info ("  正式赛 keepalive 已运行 pid=" + ($ok.ProcessId -join ',')) }
  else { Info "  ⚠ 未检测到 _official_keepalive.py，请查看 var/_official_console.err" }
  if (Test-Path $flag) { Info "  ✓ 官方赛哨兵在位（测试房自愈已停用）" }
  else { Info "  ⚠ 哨兵不在位！90s 内 keeper 会被拉回 —— 请立刻手工写 var\.official_mode" }
  # ★ 2026-09-17 修正一处**必然误报**：原先把 _watchdog 与真正危险的残留并列警告"会争同一账号(E002)"。
  #   但 watchdog 在官方模式下**不启不杀任何进程**（只暂停测试房自愈，代码已核），
  #   且 _ensure_all.py 在官方模式下**本来就会保证 _watchdog.py 活着**（赛后删哨兵即可恢复自愈）。
  #   ⇒ 19:00 切换后 watchdog 必然在跑 ⇒ 旧写法每次都打假警报。这里把它单独归为"预期且在位"。
  if ($ok -and $residW) { Info ("  ✓ watchdog={0}（预期：官方模式下它只暂停自愈、不碰进程；赛后删哨兵即恢复）" -f @($residW).Count) }
  if ($residK -or $residM -or $residA) {
    Info ("  ⚠ 仍有**会争同账号**的测试房进程：_keeper={0} match_super={1} _ab_driver={2} —— 可能 E002，请立刻处理" -f @($residK).Count, @($residM).Count, @($residA).Count)
  } elseif (-not $residW) { Info "  ✓ 无测试房 keeper/match_super/ab_driver 残留" }
}
