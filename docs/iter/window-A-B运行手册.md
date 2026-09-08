# 正式赛窗口 A/B 运行手册（SpeedE vs SpeedH）

## 窗口前（开赛 ≥30min）
1. python -X utf8 -m unittest discover -s tests        # 全绿
2. python -X utf8 tools\preflight.py                    # READY
3. 席位令牌 ×4（用户提供）：2×speedE + 2×speedh
4. 每席：run_bot.py <tok> --strategy speedX --log logs/w<序号>_<席>.log
   （keep_alive 托管可选）
## 窗口期
5. 无人工干预；409/502 自愈；日志停滞 >3min 才人工
## 窗口后
6. python -X utf8 tools\window_audit.py --logs "logs/w<序号>_*.log"
   → 裁决 JSON（n/delta/CI/verdict）
7. 席位健康：grep 409|Traceback 计数 + 场次完成率
8. replay_fetch <tid> 拉复盘 → var/replays/<tid>/（失败则用
   run_bot --record-replays 的本地事件流兜底）
9. 填裁决卡 → 晋级（合入 run_bot 默认+演进史）或 负结果登记（docs/iter/queue.md）

## 判定门槛（两段式，2026-09-07 修订——缩短候选周期）
- **第一段快筛（n≈40-60 局，~1.5h）**：δ < -1.0/场 → 立即枪毙登记（负方向
  无需高置信，真实优势翻负概率极低）；-1.0 ≤ δ ≤ +0.5 → 停（DRAW 预期）；
  δ > +0.5 → 续跑终裁段。
- **第二段终裁（累计 n≈150 局，~1h 窗口流速）**：
  行为面大改候选（如 SpeedK：副露决策/多向听选择）：**δ ≥ 1.5/场 且 95%CI 排除 0
  → WIN**（σ≈10.5@n150 下可判，1.5 为行为面候选的量级线）；
  口径级微调候选维持 δ ≥ 2.0 硬线（历史 E/F/x1 均为该族，判据从严防误纳）；
  CI 含 0 或低于对应线 → DRAW/converged（登记防重）。
- 依据：真机同桌 σ≈11（实测），δ=2 在 n=150 时 CI 半宽 ~1.76；
  早期停止只用于"枪毙/停跑"方向（筛掉明显无望者），正结论仍须终裁段全样本。
- 异常场次 <5% 否则该窗口作废。

> P0 探针结论（2026-09-07）：过胡合法；暗杠被服务器接受但 game.py 长度模型需适配杠后补牌——SpeedH 上线前必须先合入协议层适配（见 docs/iter/reports/P0-probe.md）。
