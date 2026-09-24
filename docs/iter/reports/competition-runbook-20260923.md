# 比赛运行手册（2026-09-23 起草，赛前 T-24h 复核）

> 目标：比赛当天**只用一条已验证的臂**，任何时刻都能在 5 分钟内回滚，
> 并且全程有判据、有留档、有监控。本手册的所有命令**均已在本机验证过**。

## 0. 交付物清单（赛前必须齐）

| # | 交付物 | 位置 / 命令 | 现状 |
|---|---|---|---|
| 1 | 一条**真机验证过**的臂 | `var/_keeper_strategy.txt` + `run_bot.py` 注册项 | c151（在役战役）、候选 `speedvalue` / 役 3 / 役 4 已就绪 |
| 2 | 回滚臂 | `_keeper_strategy.txt` 写回上一代已验证臂 | 机制已存在（`ab_adopt` / `_keeper.py`） |
| 3 | 判据工具 | `var/_gate2.py`（和牌率端点，fail-closed） | ✅ 已写并自检（覆盖/房数不足会 REFUSE） |
| 4 | 预检 | `python -X utf8 tools/preflight.py` | ✅ 最近一次 READY（延迟 p99=32ms） |
| 5 | 熔断 | `python -X utf8 var/_breaker_watch.py --since <TS>` | ✅ 两档 OK |
| 6 | 数据管道 | `var/_fetch_loop.py`（只读、限速、20 分钟一轮） | ✅ 已常驻（pid 记录见 `var/_fetch_loop.out`） |
| 7 | 证据链 | `docs/iter/journal.md` R1000~R1039 + `docs/iter/reports/*` | ✅ |

## 1. 赛前 T-24h 检查（逐条跑，全绿才开赛）

```powershell
cd D:\hangzhouMaj
# ① 预检：版本/fan-calc/引擎单测/延迟/自愈链
python -X utf8 tools/preflight.py                     # 期望：体检结果: READY

# ② 熔断余量（把 <TS> 换成当前战役起点）
python -X utf8 var/_breaker_watch.py --since "<TS>"   # 期望：快档/慢档都 OK

# ③ 注册 + 三档冒烟 + M=10 一条龙（幂等；战役期间**会 REFUSE**，这是预期的 fail-closed）
python -X utf8 var/_prep_next_campaign.py --arm <臂名> --module <模块> --class <类名>
#    例：--arm speedvalue --module bot.speedvalue --class SpeedValue
#    例：--arm speedvaluemeldmore0chigang --module bot.speedvaluemeldmore0chigang --class SpeedValueMeldMore0ChiGang
#    （旧的分臂脚本 _prep_register_*.py 仍可用作仅注册）

# ④ 三档冒烟（真机局面；三条命令都要过）
python -X utf8 tools/arm_smoke.py --arms <臂名> --n 25 --kind draw
python -X utf8 tools/arm_smoke.py --arms <臂名> --n 25 --kind window-live
python -X utf8 tools/arm_smoke.py --arms <臂名> --n 25 --kind window-claim

# ⑤ 判据端点可算（房数/覆盖不足会 REFUSE，这是**预期行为**）
python -X utf8 var/_gate2.py --since "<TS>" --baseline <基线臂> --candidate <候选臂> --mechanism melds|gangs|none

# ⑥ 进程体检（注意：比赛进程是 pythonw.exe，按名字过滤会误判「没有进程」）
Get-CimInstance Win32_Process -Filter "Name like 'pythonw%'" |
  Select-Object ProcessId,@{n='role';e={ if($_.CommandLine -match '_watchdog'){'watchdog'}
    elseif($_.CommandLine -match '_keeper'){'keeper'} elseif($_.CommandLine -match 'match_super'){'match_super'}
    elseif($_.CommandLine -match 'run_bot'){'run_bot'} else {'other'} }} | Format-Table
# 期望：watchdog / keeper(或 ab_driver) / match_super / run_bot 各 1
```

## 2. 采用（切换）目标臂

```powershell
# 预登记路径（dry-run 先看）
python -X utf8 tools/ab_adopt.py <臂名> --dry-run          # 会打印判据是否达到
python -X utf8 tools/ab_adopt.py <臂名> --force            # 强制采用（会在日志留痕）
# 采用动作 = ab_ctl stop → 写入 var/_keeper_strategy.txt → 记 var/_ab_adopt_log.jsonl
```
- 采用后**核对三点**：① `var/_keeper_strategy.txt` 内容 = 目标臂；
  ② 10 分钟内出现新的 `var/replays/auto_*/`（新房的决策日志）；③ `var/auto_ranking.jsonl`
  末尾出现 `"strategy": "<目标臂>"` 的行。

## 3. 比赛期间监控（每 1~2 小时一次，全部只读）

| 指标 | 命令 | 警戒线 | 动作 |
|---|---|---|---|
| 进程 | 见 §1⑥ | 任一角色缺失 >5 分钟 | 交给自愈链；**只重启缺失的那个**，绝不批量杀 |
| 决策延迟 | `python -X utf8 tools/preflight.py` | p99 > 300ms（窗口 1s/3s） | 降低并发（暂停自对弈批次） |
| 提交失败率 | `python -X utf8 var/_sub_audit.py` | 409 占比 > 3% | 检查版本/相位；考虑回滚 |
| 熔断 | `python -X utf8 var/_breaker_watch.py --since "<TS>"` | 余量转负 | **立刻回滚** |
| 判据 | `python -X utf8 var/_gate2.py ...` | z ≤ −1.50 | 回滚 |
| 复盘覆盖 | `var/_fetch_loop.out` 尾部 | 覆盖 < 70% | 手动 `tools/fetch_room_replays.py --rooms 20 --gap 1.0` |

## 4. 回滚（一键，目标 < 5 分钟）

```powershell
# ① 写回上一代已验证臂（例：speedc151）
"speedc151" | Out-File -Encoding ascii var\_keeper_strategy.txt
# ② 若 match_super/run_bot 仍在跑，先让本房自然结束（**不要**中途杀）
# ③ 需要立即切换时：杀掉 match_super 与它的 run_bot 子进程，交给 keeper 重拉
#    ⚠ 只杀这两个角色，且要用 PID 人工确认角色（见 R1003）
```
- 回滚后同样按 §2 的三点核对。
- 回滚记录写进 `docs/iter/journal.md`（时间、原因、当时判据读数）。

## 5. 红线（比赛期间不变）

1. **绝不杀** `_watchdog` / `_keeper`(或 `_ab_driver`) / `match_super` / `run_bot`
   —— 只允许在「明确卡死」时按本节 §4③ 的限定杀 match_super+run_bot。
2. **一账号一房**：不要并行开第二房。
3. 比赛期间**不改** `bot/` 既有文件、不改阈值/护栏/熔断；新臂一律**新增文件 + 注册**。
4. 判据与阈值**预登记后不中途改**（要改就走"下一役 + 新预登记"）。
5. 任何"临时脚本"用完**改 no-op**（`var/_neutralise33.py` 的做法）。
6. **★ 测试与比赛物理隔离（R1149 新增）**：比赛令牌（`var/.token_<赛事>_<日期>`）**只跑比赛**；
   一切令牌/链路/协议验证**一律用测试房令牌**（`var/.global_token` + 自动房）。
   **绝不用比赛账号做实验** —— `POST /api/match`、直连 register/ready、建测试房，**全算实验**。
   （2026-09-23 三测当晚我违反过一次：拿跑着三测的账号开自动房。）
7. **★ 禁止中途挂客户端（R1149 新增）**：房**已开打**才接 `run_bot` ⇒ 必然形态错位
   （实测护栏触发率高出正常房 3~20 倍，该房 rank4 / −184）。要对齐必须**从发牌第一手进场**。
   验证链路一律用 `python -X utf8 tools/match_super.py --rooms 1`（match 成功后**立刻**拉起
   run_bot，天然从头发牌）——不要拆成"先只 match、后单独接"两步。
   注：`POST /api/match` 幂等（重调返回原房）、**无"取消预占"端点** ⇒ 一旦误开房，只能打完整收尾。

## 6. 已知风险与对策

| 风险 | 证据 | 对策 |
|---|---|---|
| 自对弈台在**副露/杠**轴上有 +26% 保真度缺口 | R1008 / R977 | 该轴只在真机判（役 3/役 4 已如此设计） |
| 净分端点分辨率不足 | R1037：MDE@150 = ±33.4 净胜/房 | 判决改用复盘和牌率端点 |
| 第一率噪声极大 | R1037：需 427 房/臂 | 只作护栏 |
| 复盘发布延迟 | `_camp_integrity` 曾 52.7% 覆盖 | `var/_fetch_loop.py` 常驻补拉 |
| 比赛进程名是 pythonw | R1003 | 按 CommandLine 关键字 + PID 人工确认 |
| 平台 409（窗口已关） | `_sub_audit`：claim 1.7% / pass 0.76% | 属正常范围；>3% 才处理 |


---

## 7. 役切换清单（一个月约 8~10 次，照着做）

> 关键事实：**切换已全部工具化** —— `tools/ab_ctl.py start <基线> <候选> [rooms]` 会
> 写 `var/.ab_mode`（含起始时间）→ 停 keeper → 拉起 `var/_ab_driver.py`；
> `tools/ab_ctl.py stop` 删哨兵，本轮结束后驱动自行退出（watchdog 会把 keeper 拉回来）。
> **不要手工杀进程、不要手改 `.ab_mode`。**

### 7.1 判定（役结束或攒够房时）

```powershell
python -X utf8 var/_gate2.py --since "<本役 started>" --baseline <基线臂> --candidate <候选臂> --mechanism melds|gangs|pairs|none
```
- 主端点 = 复盘**和牌率/房**（z≥1.50、各 ≥80 房、覆盖 ≥70%）；副端点 = 复盘番/房（同号）；
- 护栏 = ledger 第一率（候选 ≥ 基线）+ ledger 净分同号；机制核对 = 声明的机制量同向且和牌率不降；
- 输出三种：**ADOPT / REJECT / REFUSE·CONTINUE**（房数或覆盖不足一律 REFUSE —— 这是设计行为）。

### 7.2 ADOPT（采用候选）三步

```powershell
# ① 停本役（本轮结束后驱动自然退出；不要中途杀房）
python -X utf8 tools/ab_ctl.py stop
# ② T-6h 一条龙：注册 + 冒烟 + M=10（**机器空闲时**才会执行，否则 REFUSE）
python -X utf8 var/_prep_next_campaign.py --arm <下一候选> --module <模块> --class <类名>
# ③ 起下一役：<新基线> = 刚采用的臂，<下一候选> = 下一个待测臂
python -X utf8 tools/ab_ctl.py start <新基线> <下一候选> 1
```
- 若用 `ab_adopt.py` 走项目原有采用路径，**先 dry-run** 看判据；与 `_gate2.py` 结论一致才 `--force`，
  并在 journal 里写清"新端点判据 + 原冻结判据"两个读数（口径不同，不是矛盾）。
- 若候选是**组合臂**（多轴），`ab_ctl.py start ... --bundles=<候选>` 让采用阈值走 bundle 档。

### 7.3 起役后 3 点核对（10 分钟内）

1. `var/_keeper_strategy.txt` == 新基线（或 `var/.ab_mode` 内容正确）；
2. 出现新的 `var/replays/auto_*/`（新房的决策日志）；
3. `var/auto_ranking.jsonl` 末尾出现 `"strategy": "<新臂>"`。

### 7.4 CONTINUE / REJECT

- **CONTINUE**（z<1.5 且未达负向）：继续攒房到 **≥80 房/臂**（和牌率端点）；净分端点则 ≥150；
  期间每天补拉复盘（`var/_fetch_loop.py` 常驻已做）。
- **REJECT**（z ≤ −1.5，或机制核对 FAIL 且和牌率下降）：
  ① `_gate2.py` 留档；② 写 journal（读数 + 结论）；③ 基线不变，直接进入**下一个预登记候选**。

### 7.5 每役必须留档

- 预登记文档：`docs/iter/reports/prereg-<役>-<日期>.md`（臂定义、轴、主/副端点、机制预测、已知风险）；
- 判词：journal `R####` + `var/_ab_adopt_log.jsonl` + `var/gate_report_*.txt`（若用原链路）；
- 复盘点：`var/_replay_model.py` 的规范数字（和牌率/副露/对子档案）。


---

## 8. 正式赛切换（official mode）——赛前必做，别用临时脚本

> 项目已有成套工具：`var/_switch_to_official.ps1`（5 步）、`var/_official_status.py`、`var/_exit_official.py`、
> `tools/rules_guard.py`、`tests/test_official_mode.py`。**照它们走，不要自造流程。**

```powershell
cd D:\hangzhouMaj
# ⓪ 换新令牌 + 新赛事 id（旧令牌读不到新赛事：实测 404 TOURNAMENT_NOT_FOUND）
#    令牌文件示例：var\.token_<赛事>_<日期>
# ① 先看状态（用新赛事 id / 新令牌）
python -X utf8 var/_official_status.py --tid <t_xxx> --token-file var\.token_<...>
# ② 规则一致性硬门禁（退出码 0 才允许上场；2=不一致；3=读不到）
python -X utf8 tools/rules_guard.py --strategy <臂> --token-file var\.token_<...>
# ③ 正式赛切换（会自动做 preflight → rules_guard → 写 .official_mode/.official_spec.json → 起 official 运行）
powershell -ExecutionPolicy Bypass -File var\_switch_to_official.ps1 -Strategy <臂> -TokenFile var\.token_<...> -TournamentId <t_xxx> [-DryRun]
# ④ 赛后退出
python -X utf8 var\_exit_official.py
# ⑤ 恢复役 2（★必须带 --bundles=speedc151，否则 .ab_mode 与起役时不一致
#    ⇒ 判词阈值会从组合臂 |t|≥1.50 变成单变量 1.96）
python -X utf8 tools/ab_ctl.py start speedc151,speedvalue 1 --bundles=speedc151 "--started=2026-09-23 03:13:44"
```

- **`.official_mode` 存在时**：`_ab_driver` 直接退出、keeper/match_super 被拦 ⇒ 不会再有测试房与正式赛并发（E002 同账号两房）。
- **规则开关**：`rules_guard` 返回 **2** 时**禁止上场** —— `YouCaiBiKao=true` 用 `ycbk_twins` 的双胞胎；
  `false` 用普通候选（详见计划 §O）。
- **赛前 3 分钟复检**：`python -X utf8 tools/preflight.py`（READY）+ `var/_official_status.py`（资格/阶段正常）
  + `tools/official_latency_audit.py`（延迟不超窗口）。


### 8.1 彩排与实战纪律（2026-09-23 已实测）

- **赛前彩排**（零副作用，已实测：哨兵不写、spec 不变、进程不动）：
  `powershell -ExecutionPolicy Bypass -File var\_switch_to_official.ps1 -Strategy <臂> -DryRun`
- **实战前置条件**：必须**等当前房自然结束**（脚本在 `run_bot`/`match_super` 仍存活时 **exit 2**；`_ab_driver` 残留 **exit 3**）——
  **不要中途杀房**，否则会丢一房数据并可能触发 E002。
- **护栏证据**：`tests/test_official_mode.py` **10/10**（官方赛期间 match_super / keeper / run_bot 全被拦）。


### 8.2 赛前测试复验（2026-09-23 已跑，全绿）

```powershell
cd D:\hangzhouMaj
# ⚠ 必须用 -m unittest（直接 python tests\xxx.py 会因缺少仓库根而误报 ModuleNotFoundError）
foreach ($t in @('engine_v21','fan_golden','hu','shanten_exact','shanten','sim','protocol','model',
                 'replay_recorder','official_spec','exit_official_guard','rules_guard','ab_start_guard',
                 'ab_stop_guard','ab_driver_selfguard','ab_mode','rate_guard','arm_smoke',
                 'official_mode','replay_model','ycbk_twins')) {
  python -X utf8 -m unittest "tests.$t"
}
```
- 期望：**全部 OK**（2026-09-23 实测 21 个文件全绿）。
- 覆盖：番型/爆头/七对/白板规则、向听、模拟、协议、录制，以及 official / AB / 限速护栏与臂冒烟。


### 8.3 赛前 30 分钟：延迟与负载纪律（R1058）

**为什么**：正式赛真实配置是 **碰/吃窗口 1s、出牌 3s**（`M=10, Rounds=16`，见 `docs/开赛操作单-20260917.md` §27.5）。
实测 M=10 压力下我们的候选臂 **claim p99 ≈ 0.65~0.79s，且有 0.2~0.55% 的 claim 超 1s**；
而出牌 p99 ≈ 1.2~1.3s（3s 窗口）。

```powershell
# ① 停掉所有占用 CPU 的批次/分析（这/这些正是 M=10 级竞争的来源）
#    自对弈批次：_arena_duel.py 进程；重分析脚本：本会话的 _*.py 分析
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '_arena_duel' } |
  ForEach-Object { Write-Host "需人工确认后停止: pid=$($_.ProcessId)"; }
# ② 复检：机器空闲 + 最终臂的极端负载表现
python -X utf8 tools/preflight.py                     # 期望 READY（含决策延迟体检）
python -X utf8 var/_concurrency_bench.py <最终臂类> --from-file var/smoke_corpus_v1.jsonl `
        --threads 10 --per-thread 200 --warm 0 --kind window
# 期望：超 1s 计数尽量为 0（历史参考：speedvalue=4 / Tol2Chi=9 / Tol4Chi=9，属可接受量级）
# ③ 然后按 §8 执行 official 切换
```
- 我们账号**一次只打一房** ⇒ 真实负载远低于 M=10；**只要机器空闲**，单线程 p99 ~120ms，1s 窗口无风险。
- **不要**在正式赛期间跑自对弈/分析脚本；也不要临时改策略。


### 8.4 `OnlineConfirm=true` 的时间线纪律（R1061 核实）

正式赛配置要求 **开赛前 90s 内必须有"已认证请求"**，且**每个阶段**都要重新 `ready` 出席确认。

```powershell
# T-30 分钟：只读看状态 → 提交一次 ready（幂等）
python -X utf8 var/_ready_1024.py --tid <t_xxx> --token-file var\.token_<...> --status
python -X utf8 var/_ready_1024.py --tid <t_xxx> --token-file var\.token_<...>
# T-5 分钟：再提一次（保险）
python -X utf8 var/_ready_1024.py --tid <t_xxx> --token-file var\.token_<...>
# 确认 keepalive 的 run_bot 在跑（它持续长轮询 = 已认证请求，天然满足 90s 要求）
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_bot\.py' } |
  Select-Object ProcessId,CreationDate
```

**多阶段链路（代码已核实，`bot/protocol.py`）**：
`registering → running → stage_done → stage_open → running → …（决赛加赛）→ finished`；
`stage_open` 且名单内有资格 ⇒ **自动 confirm**（每阶段都确认）；名单外（被淘汰）⇒ 自动退出；只有 `finished/closed/void` 才算终态退出。
⇒ 打完一个阶段**不会**被卡住，也不会重复确认；我们只需保证 `run_bot` 一直活着（keepalive 负责）且令牌是**本场**的。


### 7.6 切换点附加的工程步骤（2026-09-23 06:4x 追加，见计划 §U-6）

> 目的：**不为工程项单独占一役**，把它拆成两次切换点的附加动作（各一步，均有 fail-closed 补丁器）。

| 切换点 | 附加动作 | 预期产出 |
|---|---|---|
| **役 2 起役时** | `python -X utf8 var/_prep_window_instrument.py`（**零行为变更**，只给决策日志加 `rnd`/`age_ms`） | 役 2 判词 **+ `age_ms` 基线（预期 p50 ≈1.2s）** |
| ~~**役 3 起役时**~~ | ~~`python -X utf8 var/_prep_hybrid_state.py` 然后设 **`HM_HYBRID_STATE=1`**~~  ——⚠ **已否决并关闭（不得在赛前重开）**：hybrid `/state` 实测 p50 744→3768ms（登记竞态）⇒ 客户端已定终态（见本文 §9.1） | —— **不做** |

- 两个补丁器都是**幂等 + fail-closed**（检测到在役进程或新鲜房日志即 REFUSE），且都已在**副本**上彩排通过。
- ~~**开关（役 3 起役时）**~~ ——⚠ **已否决并关闭（不得在赛前重开）**：hybrid `/state` 实测 p50 744→3768ms（登记竞态）⇒ 不做（见 §9.1）。原文保留：推荐**哨兵文件** `var/.hybrid_state`（与 `.official_mode` 同约定，**自愈重启也不会丢**）；
  也可用 `$env:HM_HYBRID_STATE="1"`（仅对当次由该 shell 启动的进程生效 —— 自愈链会重启进程且**不带 env**，届时开关会静默失效）。
- 验证（工程效果）：`python -X utf8 var/_window_age_report.py`（分类）+ `python -X utf8 var/_window_match_content.py`（捕获率）
  → 目标 **捕获率 ≥90%**、`age_ms` p50 ~1.2s→~0.6s、**409 不升**、真机和牌率 z≥1.50。


---

## 9. 2026-09-23 10:3x 更新（今日验证结论固化）

### 9.1 客户端终态（**比赛期间不得改动**）

| 项 | 状态 | 依据 |
|---|---|---|
| `window_watch=6`（弃牌后 6 批必取快照） | ✅ 生效 | 服务端响应者名单可能延迟登记；跳过快照会让"看到的窗口 -31%、吃实现 -50%"（R1113） |
| R1095a（吃碰杠后从本地河移除该牌） | ✅ 生效 | 河保真：扣吃碰口径 0.90 少 / 0.00 多（门禁 <=1.5） |
| R1096（响应 409 不整体重同步） | ✅ 生效 | 事件连续性；代价 ~4% 调用 |
| `calls_per_event` | 0.65-0.67 | — |

**已否决并关闭（不得在赛前重开）**：hybrid `/state`（登记竞态 ⇒ p50 744→3768ms）、缓存窗口决策（吃相位不可推导 ⇒ 91/73 条 409 哨兵已删）、客户端"省 /state 调用"（两次实测：换不来捕获也换不来延迟）。

### 9.2 比赛当天链路（已逐项实测）

1. `tools/preflight.py` → **READY**（v34 一致 / fan-calc 6/6 / 引擎单测 / run_bot 单实例 / 决策 p99=47ms / 自愈链 Ready）；
2. 换**本场新令牌** → `tools/rules_guard.py --strategy <臂> --token-file <新令牌>`：
   `true` ⇒ 注册并使用 `*YCBK` 双胞胎（4 个均已验证、GOD_MELD=False）；`false` ⇒ 常规臂；**rc=3 ⇒ 不参赛**（fail-closed）；
3. `var/_switch_to_official.ps1 -Strategy <臂> -TokenFile <新令牌> -TournamentId <t_xxx>`（**先 `-DryRun` 复核**，实测零副作用）；
4. 赛后 `var/_exit_official.py`。

### 9.3 停止 A/B 的唯一正确方式

**只能用 `tools/ab_ctl.py stop`**（它等驱动把基线写回 `var/_keeper_strategy.txt`）。
驱动在役期间会把**当前臂**写进该文件；**强杀驱动会跳过写回**（line 422），watchdog 会把未验证的候选拉成生产策略（09-15 事故类型）。

### 9.4 赛前 7 天必做

停试验 → 复跑 M=10 bench → 重跑 preflight → `rules_guard`（新令牌）→ 整链 official **实跑一次**（DryRun 之外）→ 冻结配置并记录 keeper 策略与回滚点。
