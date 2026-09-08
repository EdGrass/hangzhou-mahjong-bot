# 迭代轮次流水（journal）

> 每轮一行记录。轮 = 一次自迭代循环（一个候选从入队到出结论，或一轮基建/修复）。
> 格式：`- [轮次|日期] 做了什么 → 结论（证据见 reports/<id>.md）`

- [R0 | 2026-09-06] 阅读全项目，产出 docs/自迭代方案.md（双环门禁协议）与
  docs/iter/{queue,journal}.md；建立 Goal goal-4b4c1d3e；脚手架 tools/ab_gate.py；
  C001 speedx1 实现并注册，启动 L1。
- [R1 | 2026-09-06] C001 L1 全流程：
  - 单测 80 OK / stability ALL PASS（x1 0 违规守恒，胡率≈E）；
  - 6 批同桌面 A/B（seed 11-16，1200 局 history + 187 partial = 1387 game-level）；
  - **实测校准 σ_d≈33（推翻 σ=10 旧假设）** → tools/ab_analyze.py 入库 + ab_gate
    --sigma + docs §6 更新；δ=2 需 N≈1030；
  - **裁决 WIN**：delta +2.17/场（CI [+0.33,+4.02]，σ=32.6）→ 送 L2，等 cookie；
  - 清理 9/3 遗留 heuristicAx4 无限循环僵尸进程（39460，污染 var/arena 数据源）；
  - 报告卡 docs/iter/reports/C001.md；台账 var/iter/ab_runs.jsonl（gitignore）。
- [R2 | 2026-09-06] C001 L2 启动 + C002 实现：
  - 用户提供 cookie（有效至 10-05）→ 建房 t_fb08f23caa81（M=1 rounds=1）：
    speedx1×2(青龙/白虎) + speedE×2(朱雀/玄武) 真机同桌，tools/l2_watch.py
    看门狗托管，tools/l2_audit.py 逐场审计（~1.5min/局 → 200 局 ~5h 后台）；
  - **fix(run_bot)**：c602d33 误删 bot.util 导入 → 真机入口 NameError；
    教训：run_bot 入口改动必须过 --smoke（已恢复导入）；
  - C002 speedx2 实现（SpeedG 思路重建于 E：听牌等待扣已见；sim 注入 river），
    单测 3 项 + 全量 83 OK + stability ALL PASS；6 批 A/B（seed 21-26）并行中。
- [R3-R10 | 2026-09-06 22:00-02:45] C001 L2 真机同桌全流程（多会话主管 l2_super）：
  - 服务器重启清房（~80min 周期，实测 21:50 一次）→ l2_super 自动建房续跑；
  - 单会话 t_b24d73abd1f4 连续 4.7h 跑满 **n=200 场**（1.5-2min/场）；
  - **终裁：DRAW/converged** —— delta +0.53/场（σ=11.03 真机实测，
    CI [−1.00, +2.06] 含 0）：L1 的 +2.2 优势真机不可复现 → 不保留（E/F 先例）；
  - 教训：真机 δ 轨迹首 60 场正漂移（+2.1@63）后回归 0.5 —— n<120 判定不可信；
  - C003 参数化落地（wall_reserve 可配，默认不翻 60）；
  - C004 标注方法学限制（防守类需真防守对手，两门禁均测不出）；
  - 清理轮：speedx1/speedx2 代码+注册删除（实验分支不保留），81 tests OK +
    stability ALL PASS；PROJECT.md §4/§7 演进史更新。
  - **目标闭环完成**：C001 L1 结论 + C002 完整判定 + C001 L2 终裁（防假阳性
    合入的演示）→ 防重登记表更新（C001/C002 + F/G/x1/x2 族收敛结论）。
  - 用户提供 cookie（有效至 10-05）→ 建房 t_fb08f23caa81（M=1 rounds=1）：
    speedx1×2(青龙/白虎) + speedE×2(朱雀/玄武) 真机同桌，tools/l2_watch.py
    看门狗托管，tools/l2_audit.py 逐场审计（~1.5min/局 → 200 局 ~5h 后台）；
  - **fix(run_bot)**：c602d33 误删 bot.util 导入 → 真机入口 NameError；
    教训：run_bot 入口改动必须过 --smoke（已恢复导入）；
  - C002 speedx2 实现（SpeedG 思路重建于 E：听牌等待扣已见；sim 注入 river），
    单测 3 项 + 全量 83 OK + stability ALL PASS；6 批 A/B（seed 21-26）并行中。

- [R11 | 2026-09-08 危机处置 P1-P2] 只读诊断 + 三层新证据 + 基建落地：
  - 引擎 v21 口径漂移实锤并修复（4白板爆头撤销旧裁、白x4 无落单才计豪华组；
    黄金集 132→140 在线刷新全对齐；tests/test_engine_v21.py 9 项锚定服务器实测）；
  - 复核全部历史会话（tools/session_health.py 新工具）：w1 实为 n=318 δ+0.27
    （原记 150/+0.47 是早期快照）；w2 实为 n=21 δ-4.71（原记 -6.8@12 有误）；
    裁决无一翻盘但可信度普遍不足（health-audit-2026-09-08.md）；
  - 座位组合分解新证据：同策略混配按绝对占位分组 δ 差 ±5-11/场
    （k1 占(1,2)=+6.8 vs 占(1,3)=-5.1）→ 座位结构效应 ≥ 候选效应量级；
  - 时延假说被本地实测否决：E/U/V decide p95<0.03ms（600 手）→ 409 席位
    不对称与决策算力无关，机制不明（席位/令牌级随机分量）；
  - 基建：决策录制（<gid>.dec.jsonl 全局面快照+耗时+提交结果）、[dperf] 慢决策、
    [xlog] 通用分歧探针（非 E 自动开）、409 按 phase/action 细目、l2_super 全会话
    自动 --record-replays（每席独立目录）；
  - 停 v3 关房 → 启动 E×4 座位偏倚标定（e4a，房 t_a50d02b13be4，全 speedE）。
