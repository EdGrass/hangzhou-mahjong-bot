# -*- coding: utf-8 -*-
# `var/_prepare_submission.ps1` —— **参赛提交物准备与验收**（默认只打印/只检查；-Go 才执行 git 操作）。
#
# 为什么单独做：提交要求是"完整可运行的源码 + 使用说明"。而本仓库现状有两个坑：
#   ① **442 个未追踪文件**（绝大多数 bot/ 臂、documents 都在其中）⇒ 只 push 已追踪内容 = 源码不完整；
#   ② **模型文件在 var/ 里，而 var/ 被 .gitignore 忽略** ⇒ 必须 `git add -f`，否则源码"看起来完整但臂全退化成 no-op"。
#
# 用法：
#   pwsh -NoProfile -File var/_prepare_submission.ps1                 # 只检查（不碰 git）
#   pwsh -NoProfile -File var/_prepare_submission.ps1 -Go             # 执行 add/commit（不 push）
#   pwsh -NoProfile -File var/_prepare_submission.ps1 -CloneVerify    # 额外：clone 到临时目录跑 --smoke
#
# 注意：**push 需要你先建好远程仓库**（`git remote add origin <url>`）——本脚本不替你建仓库、也不 push。

param(
  [switch]$Go,
  [switch]$CloneVerify,
  [string]$Root = "D:\hangzhouMaj"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$deliverables = @("requirements.txt", "README.md", "docs/参赛说明.md")
$models = @(
  "var/c073_orig_w2_net.pt",     # BC 排序网
  "var/c121_meld_net.pt",        # 学习副露网
  "var/c089_ranker_net.pt",      # 教师排序器
  "var/baotou_v1.pt"             # 爆头可达性 V（★ 新增：早期笔记只写了 3 个模型，现在是 4 个）
)
# ★ R1345：**运行期基础设施脚本**（都住在被 .gitignore 忽略的 var/ 里）⇒ 必须单独 `git add -f`。
#   为什么必须：提交要求是【完整可运行 + 能**接入官方对战平台**】，而这 28 个脚本**正是【接入】那条链**：
#   keeper/watchdog/ensure_all（自愈）→ _switch_to_official.ps1（切入官方模式）→ _ready_1024.py（POST /ready 到位）
#   → _official_keepalive.py + _official_guard.py（官方对局与看护）。缺了它们，clone 下来只能跑 run_bot.py，**接不进比赛流程**。
$opsScripts = @(
  "var/_keeper.py",
  "var/_watchdog.py",
  "var/_ensure_all.py",
  "var/_official_keepalive.py",
  "var/_official_guard.py",
  "var/_official_status.py",
  "var/_ready_1024.py",
  "var/_ab_driver.py",
  "var/_verdict_watch.py",
  "var/_gate2.py",                # ★ R1349：**役判词执行者**（心跳与 B 段都跑它）；本轮被闭包门抢出来“未入仓”

  "var/_after_4test.py",
  "var/_enter_event.py",
  "var/_bsegment.py",
  "var/_switch_campaign.py",
  "var/_campaign_ready.py",
  "var/_ps.py",                  # ★ R1379：PowerShell 解析器（_4test_gate_precheck / _bsegment / _enter_event 都用）
  "var/_m10_latency_gate.py",  # ★ R1377：闭包依赖 —— M=10 延迟门禁（役前必跑）
  "var/_gang_now.py",  # ★ R1377：闭包依赖 —— 杠频读数（选臂包⑥）
  "var/_lowprio_run.py",  # ★ R1377：闭包依赖 —— 低优先运行包装器（读卡命令用）
  "var/_format_fidelity.py",     # ★ R1377：赛前赛制保真核对（Rounds/Kind/OnlineConfirm 等）
  "var/_pick_arm.py",            # ★ R1377：10/5–10/6 最终选臂主序列（强手房分/房 + 不可区分判定）
  "var/_seat_h2h.py",            # ★ R1377：两半 Pareto 的 B 半（同席 TOP32：赢分/轮、番/胡、爆头/胡、副露/轮）
     # ★ R1355：README/参赛说明都叫用户跑它做自检（此前未入仓 ⇒ clone 里“文件不存在”）
  "var/_apply_p0_404.py",
  "var/_4test_gate_precheck.py",
  "var/_daily.py",
  "var/_feature_mode.py",        # ★ R1345：_ensure_all.py 的同级依赖（缺它 clone 里 import 就报 ModuleNotFoundError）
  "var/_exit_official.py",       # ★ R1345：_daily.py 按路径调用
  "var/_portal_watch.py",
  "var/_c069_discard_train.py",  # ★ R1346：test_speedc069 按路径 exec（未入仓 ⇒ clone 里 FileNotFoundError）
  "var/_replay_guard.py",         # ★ R1346：test_replay_guard 按路径 exec
  "var/_replay_model.py",         # ★ R1346：test_replay_model 按路径 exec
  "var/_track_hands.py",          # ★ R1346：test_speedc220 直接 `from _track_hands import track`
        # ★ R1345：_register_portal_watch.ps1 按路径注册的看护脚本
  "var/_switch_to_official.ps1",
  "var/_switch_back_to_test.ps1",
  "var/_start_1024.ps1",
  "var/_register_4test_switch.ps1",
  "var/_register_after_4test.ps1",
  "var/_register_campaign3_watches.ps1",
  "var/_register_campaign_watches.ps1",  # ★ R1429：通用看护注册器（役 4/5：任意基线 + N 候选）
  "var/_register_gate_precheck.ps1",
  "var/_register_ladder_snapshot.ps1",
  "var/_register_portal_watch.ps1",
  "var/_register_4test_format_watch.ps1",  # ★ R1389：四测赛制观察定时器的注册脚本（只新增任务，不碰既有链路）
  "var/_register_4test_replay_fetch.ps1",
  "var/_register_4test_detail_snap.ps1",  # ★ R1391：四测详情（ranking/my_games）快照的注册脚本
  "var/_4test_watch_detail.py",             # ★ R1391：上行注册的看护（闭包依赖）  # ★ R1390：四测赛后官方复盘自动补拉（幂等重试）
  "var/_adopt_when_ready.py",           # ★ R1406：判词到点自动执行 B 段（仅 ADOPT）
  "var/_register_adopt_watch.ps1",        # ★ R1406：上行看护的注册脚本
  "var/_mech_watch.py",                  # ★ R1416：役中机制端点守护（定期重抽离线足迹）
  "var/_register_mech_watch.ps1",        # ★ R1416：上行守护的注册脚本
  "var/_switch_final.py",                # ★ R1407：10/7 换上最终臂（未选定/官方模式就拒绝）
  "var/_final_arm_confirm.py",            # ★ R1436：10/7 换臂前自动补 .final_arm.txt（人工 echo 断点的替身）
  "var/_final_switch_retry.ps1",          # ★ R1436：10/7 12:00 换臂重试（判词晚到也能升级）
  "var/_strong_slice.py",               # ★ R1437：按强手房切复盘语料（让现成工具做分层读数；口径修正）
  "var/_strong_veto.py",                # ★ R1437：强手房否决（净分/房 + 第1率 显著劣 ⇒ 该轴不采用）
  "var/_verdict_by_elite.py",           # ★ R1437：按【房里有/没有 top32】分层读役次（读卡/计划 §V.66 命令②；此前漏在闭包外）
  "var/_elite_share_by_day.py",         # ★ R1437：上行工具引用的同级模块（缺它 clone 里必断）
  "var/_final_ready_check.py",           # ★ R1407：10/7·10/8 最终就绪校验（7 项）
  "var/_register_final_day.ps1",         # ★ R1407：上两个一次性任务的注册脚本
  "var/_switch_test_strategy.py",
  "var/_final_pick_proposal.py",
  "var/_final_event_switch.py",            # ★ R1435：10/10 正式赛自动上线（缺令牌/最终臂即拒绝）
  "var/_register_final_event.ps1",         # ★ R1435：10/10 两个一次性任务的注册脚本           # ★ R1434：10/5 最终臂选择提案（只读台账+榜单）
  "var/_register_final_pick_proposal.ps1",  # ★ R1434：上行一次性任务的注册脚本      # ★ R1407：换测试房 keeper 策略（_switch_final 的闭包依赖）
  "var/_register_tminus_ready.ps1",
  "var/_prepare_submission.ps1",
  "var/_ps_syntax_check.ps1"
)
$mustTrack = @(
  "run_bot.py",
  "bot/speedvalue.py", "bot/speedc151.py", "bot/speedvaluebc.py",
  "bot/speedvaluebaotouv.py", "bot/speedvaluemeld.py"
) + $models + $opsScripts

Write-Host "=== 提交物检查（$Root）==="
$bad = 0
foreach ($f in $deliverables) {
  if (Test-Path $f) { Write-Host ("  OK   {0,-24} ({1} 字节)" -f $f, (Get-Item $f).Length) }
  else { Write-Host ("  FAIL {0} 缺失" -f $f); $bad++ }
}
foreach ($m in $models) {
  if (Test-Path $m) { Write-Host ("  OK   {0,-28} ({1:N0} KB)" -f $m, ((Get-Item $m).Length / 1KB)) }
  else { Write-Host ("  FAIL 模型缺失：{0}（相关臂会静默退化成 no-op！）" -f $m); $bad++ }
}
foreach ($f in $opsScripts) {
  if (Test-Path $f) { Write-Host ("  OK   {0}" -f $f) }
  else { Write-Host ("  FAIL 运行期脚本缺失：{0}（缺了就接不进比赛流程！）" -f $f); $bad++ }
}
Write-Host "`n=== 文案一致性门（申报正文声称的指南版本 == 代码里的）==="
# ★ R1356：申报正文会被**直接粘贴进申报页**（它描述我们怎么连平台）⇒ 它声称的指南版本必须与**打包进去的代码**一致。
#   实测：404 语义在 P0 补丁（v34→v35）前后是两套，若提交时忘了落补丁 ⇒ 会交一份“说的与做的不一样”的说明。
$codeVer = ""
$initPath = Join-Path $Root "bot/__init__.py"
if (Test-Path $initPath) {
  $m = [regex]::Match((Get-Content $initPath -Raw), "GUIDE_VERSION_KNOWN\s*=\s*(\d+)")
  if ($m.Success) { $codeVer = $m.Groups[1].Value }
}
$docVer = ""
$docPath = Join-Path $Root "docs/申报正文-最终.md"
if (Test-Path $docPath) {
  $m2 = [regex]::Match((Get-Content $docPath -Raw), "GUIDE_VERSION_KNOWN\s*=\s*(\d+)")
  if ($m2.Success) { $docVer = $m2.Groups[1].Value }
}
if (-not $codeVer -or -not $docVer) {
  Write-Host ("  FAIL 读不到版本（代码='{0}' 文案='{1}'）" -f $codeVer, $docVer); $bad++
} elseif ($codeVer -ne $docVer) {
  Write-Host ("  FAIL 文案声称 v{0}，但代码是 v{1} ⇒ **先落 P0 补丁再提交**（或把文案改回来）" -f $docVer, $codeVer); $bad++
} else {
  Write-Host ("  OK   文案与代码均为 v{0}" -f $codeVer)
}

Write-Host "`n=== 泄密门（令牌 / cookie 绝不进公开仓）==="
$leak = @()
foreach ($f in ($models + $opsScripts)) {
  if (-not (Test-Path $f)) { continue }
  if (Select-String -Path $f -Pattern '[0-9a-fA-F]{64}' -AllMatches -ErrorAction SilentlyContinue) { $leak += "64位串:$f" }
}
$trackedSet = @{}
foreach ($f in (git -c core.quotepath=false ls-files)) {
  # git ls-files 会对非 ASCII 路径加引号/十六进制转义（实测 docs/参赛说明.md 报 Illegal characters in path）
  $p2 = $f -replace '^"(.*)"$', '$1'
  $trackedSet[$p2] = $true
  if (-not (Test-Path -LiteralPath $p2)) { continue }
  $fi = Get-Item -LiteralPath $p2 -ErrorAction SilentlyContinue
  if ($fi -and $fi.Length -lt 400) {
    $c = Get-Content -LiteralPath $p2 -Raw -ErrorAction SilentlyContinue
    if ($c -match '^\s*[0-9a-fA-F]{64}\s*$') { $leak += "纯令牌文件:$p2" }
  }
}
if ($leak.Count) { Write-Host ("  FAIL 疑似泄密：" + ($leak -join ", ")); $bad++ }
else { Write-Host ("  OK   待发布 {0} 个文件均无 64 位令牌串；已追踪文件中无【纯令牌/纯 cookie 小文件】" -f ($models + $opsScripts).Count) }

$untracked = (git status --porcelain | Where-Object { $_ -match '^\?\?' }).Count
$trackedModels = (git ls-files var/*.pt | Measure-Object).Count
$trackedOps = ($opsScripts | Where-Object { $trackedSet.ContainsKey($_) }).Count
Write-Host ("  git: 未追踪文件 {0} 个；已追踪模型 {1}/{2}；已追踪运行期脚本 {3}/{4}；remote：{5}" -f `
  $untracked, $trackedModels, $models.Count, $trackedOps, $opsScripts.Count, ((git remote -v | Out-String).Trim() -replace "\r?\n", " | "))

if ($Go) {
  Write-Host "`n=== 执行 git add（代码全量 + 模型强制）==="
  git add -A
  git add -f @models
  git add -f @opsScripts          # ★ R1345：运行期脚本同样在 var/ 里，不强制 add 就不会进仓
  Write-Host "  已 add。接下来请人工确认 `git status`，再提交："
  Write-Host "  git commit -m `"submit: hangzhou-mahjong bot (complete runnable source + models)`""
  Write-Host "  git push -u origin main   （需先 git remote add origin <你的仓库>）"
} else {
  Write-Host "`n（dry-run：未执行任何 git 操作；加 -Go 才执行 add）"
}

if ($CloneVerify) {
  $tmp = Join-Path $env:TEMP ("hm_clone_verify_" + (Get-Date -Format 'HHmmss'))
  Write-Host "`n=== clone 验收 → $tmp ==="
  git clone --quiet $Root $tmp
  Push-Location $tmp
  $o = python -X utf8 run_bot.py --smoke 2>&1
  Write-Host ("  smoke exit={0}" -f $LASTEXITCODE)
  $o | Select-Object -Last 4
  Pop-Location
  Write-Host "  提示：v35 的 BREAKING 在 P0 补丁落地前必然失败，属已知项。"
}
exit $bad