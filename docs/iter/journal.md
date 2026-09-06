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
