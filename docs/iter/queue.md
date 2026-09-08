# 候选队列（Agent 自迭代）

> 协议见 docs/自迭代方案.md。状态机：queued → in-l1 → in-l2 → merged | rejected |
> dead-end | converged | paused。同一假设不得重复提交（先 grep 本文与 PROJECT.md 演进史）。

## 默认评估口径（记录于 2026-09-06，C001 实测校准 2026-09-06）

- L1 同桌面：候选×2 vs SpeedE×2，rounds=8，`sim.WALL_RESERVE` 沿用引擎默认
  （=20；C003 参数化后暂不翻 60——reserve60 本地流局 71% 失真，待 L2 真机
  统计校准；见 C003 行）。首批候选统一口径互比。
- 判据：δ_min=2.0/场；CI 含 0 即 DRAW；**σ 用实测值**（本地 8 巡同桌面 σ_d≈33，
  `python tools/ab_analyze.py <combo子串>` 逐场实测），δ=2 需 N≈1030 局（≥6 批 ×200）。
- A/B 命令：`python -m arena.runner --combo "speedxNx2+speedEx2" --games 200 --rounds 8 --seed S`
  （≥6 批不同 seed，合计 ≥1200 局，24 核可 6 批并行 ~35min）
  → `python tools/ab_gate.py --combo ... --sigma <实测>`。

## 队列

| id | 来源 | 假设（一句话） | 域 | 状态 | 备注 |
|---|---|---|---|---|---|
| C001 | PROJECT.md §7.1 / 复盘差异#2 | tie 内弃刚摸优先（TOP 打新张 vs 我们留新张） | strategy | converged | **L1 WIN(+2.2) → L2 真机 200 场 δ+0.5 CI 含 0 → converged 不保留**（报告 C001.md 终章；教训：真机 n<120 不可信、首 60 场正漂移是选择效应） |
| C002 | PROJECT.md §7.5 | 已见牌扣减重试（SpeedG 思路，曾就绪被清） | strategy | dead-end | **L1 DRAW**：1200 局 +0.19/场 CI 含 0（报告 C002.md）；sim river 注入保留给 C004 |
| C003 | PROJECT.md §7.4 | 短局口径参数化（WALL_RESERVE） | eval | paused | **参数化已完成**（sim/runner --wall-reserve + 测试）；**默认口径不翻 60**：reserve60 本地流局 71% 失真、旧复盘被 timeout 污染非干净源 → 待 L2 真机 n≥200 的流局/局长统计校准后落定 |
| C004 | PROJECT.md §7.2 | 防守 v0：弃牌河危险度回避（安全牌序） | strategy | paused | **方法学限制（分析结论 2026-09-06）**：防守收益只在"对手会听牌/防守互动"时体现；本方案两个门禁的对手=自家 speed 系（L1 sim / L2 真机同桌均无真防守对手）→ 测不出防守价值，本地跑分会假阴性。若要做：只能正式赛参赛窗口实测（人工通道），或先造"会防守的陪练对手"。实现蓝图（river 已就绪 + tie 内安全排序）保留 |
| C005 | PROJECT.md §7.3 | 打点 EV 分支（4 白/爆头/财飘取舍；过胡合法性已由 P0 证实） | strategy | queued | 复用 fan-calc 黄金集；P0 过胡实测后可行性成立 |
| C007 | 牌效理论吸收（用户提案，K1+K2） | 全向听级一步有效牌 tie（K1，补 F 只做 s==1 之缺）+ 副露 ukeire 判据（K2，碰/吃/直杠按有效牌而非仅向听快） | strategy | in-dev | speedk（SpeedE 派生，run_bot opt-in）；依据：牌效综述（搭子/复合形/有效牌重复）；预期：小但为 E 系未测行为面（副露效率） |
| C006 | MCTS | 搜索型决策 | strategy | queued | 远期，队列空后议 |

## dead-end / converged 登记（防重，先看这里）

| 条目 | 证据 | 教训 |
|---|---|---|
| SpeedF（精确 ukeire 25ms） | 真机同桌 408 局与 E 统计不可分（PROJECT.md §4） | 计算更精 ≠ 可判更强；δ<2/场 量级不值得再试 |
| C001/speedx1（tie 弃刚摸） | **L1 WIN(+2.2/1387局) → L2 真机 200 场 δ+0.5 CI 含 0（2026-09-06）** | 本地衰减第三次复现（同 SpeedB/E/F 结构）；L1 只当筛子；真机 n<120 判据不可信 |
| C002/speedx2（已见牌扣减） | L1 1200 局 +0.19/场 CI 含 0（2026-09-06） | 评估精度类改进连续两代（F/G/x2）不可分 → 该族封存 |
| SpeedH/speedh（杠/链 EV 门控） | **正式赛窗口 W1 318 场 δ+0.27（150 场快照 +0.47 继续衰减；复核 2026-09-08）CI 含 0（2026-09-07）** | 安全杠 150 局 0 触发→收益频率上限决定 <1/场；策略微调族第 5 代收敛（W1 裁决卡） |
| K1/K2 族（speedk=K1+K2；speedu=K1） | 真机会话复核（2026-09-08）：+0.73@56 / −4.71@21（原记 −6.8@12 有误，n=21 复核修正；n 小不作数）/ −1.39@18 | **ukeire/有效牌代理在財神局无大效应**（万能牌→每巡完成概率主导，结构性进张与竞速脱钩）；⚠ 上述会话候选均固定青龙/白虎或朱雀/玄武，座位组合效应 ±5-11/场未控（health-audit-2026-09-08），正负方向均需平衡设计复核 |
| ml 监督/RL 线（v0-rl5） | arena 数据 rl1-5 对 heuristicA 全 -4~-6/场；分支被整删 | 弱模型当对手时 RL 不产出可迁移策略 |
| SpeedA/B/C | 被 B/E 取代退役（演进史） | 纯向听/无条件副露已封存 |
