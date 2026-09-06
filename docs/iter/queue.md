# 候选队列（Agent 自迭代）

> 协议见 docs/自迭代方案.md。状态机：queued → in-l1 → in-l2 → merged | rejected |
> dead-end | converged | paused。同一假设不得重复提交（先 grep 本文与 PROJECT.md 演进史）。

## 默认评估口径（记录于 2026-09-06，C001 实测校准 2026-09-06）

- L1 同桌面：候选×2 vs SpeedE×2，rounds=8，`sim.WALL_RESERVE` 待 C003 落定为 60 前沿用
  引擎默认（=20 但 sim 内长局口径）；首批候选在统一口径下互比即可。
- 判据：δ_min=2.0/场；CI 含 0 即 DRAW；**σ 用实测值**（本地 8 巡同桌面 σ_d≈33，
  `python tools/ab_analyze.py <combo子串>` 逐场实测），δ=2 需 N≈1030 局（≥6 批 ×200）。
- A/B 命令：`python -m arena.runner --combo "speedxNx2+speedEx2" --games 200 --rounds 8 --seed S`
  （≥6 批不同 seed，合计 ≥1200 局，可多核并行跑批）→ `python tools/ab_gate.py --combo ... --sigma <实测>`。

## 队列

| id | 来源 | 假设（一句话） | 域 | 状态 | 备注 |
|---|---|---|---|---|---|
| C001 | PROJECT.md §7.1 / 复盘差异#2 | tie 内弃刚摸优先（TOP 打新张 vs 我们留新张） | strategy | in-l2 | **L1 WIN**（1387 局 +2.3/场 CI 排除 0），等 HM_PORTAL_COOKIE 上真机；报告 docs/iter/reports/C001.md |
| C002 | PROJECT.md §7.5 | 已见牌扣减重试（SpeedG 思路，曾就绪被清） | strategy | queued | 蓝图=git 3c269fd speedg.py；基于 E 重建为 speedx2；σ_d≈33 → 需 N≈1100+ |
| C003 | PROJECT.md §7.4 | 短局口径入默认评估（WALL_RESERVE=60） | eval | queued | 基建，影响后续所有判定；C001 判定后落地 |
| C004 | PROJECT.md §7.2 | 防守 v0：弃牌河危险度回避（安全牌序） | strategy | queued | 需 view 注入 river → 协议侧冒烟 |
| C005 | PROJECT.md §7.3 | 打点 EV 分支（4 白/爆头/财飘取舍） | strategy | queued | 复用 fan-calc 黄金集 |
| C006 | MCTS | 搜索型决策 | strategy | queued | 远期，队列空后议 |

## dead-end / converged 登记（防重，先看这里）

| 条目 | 证据 | 教训 |
|---|---|---|
| SpeedF（精确 ukeire 25ms） | 真机同桌 408 局与 E 统计不可分（PROJECT.md §4） | 计算更精 ≠ 可判更强；δ<2/场 量级不值得再试 |
| SpeedG（已见牌扣减） | 与 F 同批被清（commit 3c269fd → c602d33） | C002 需换实现路径或口径再论 |
| ml 监督/RL 线（v0-rl5） | arena 数据 rl1-5 对 heuristicA 全 -4~-6/场；分支被整删 | 弱模型当对手时 RL 不产出可迁移策略 |
| SpeedA/B/C | 被 B/E 取代退役（演进史） | 纯向听/无条件副露已封存 |
