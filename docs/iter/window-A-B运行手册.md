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
门槛：n≥200（same-table 配对，可跨窗口累积于同一裁决卡）；异常场次 <5%

> P0 探针结论（2026-09-07）：过胡合法；暗杠被服务器接受但 game.py 长度模型需适配杠后补牌——SpeedH 上线前必须先合入协议层适配（见 docs/iter/reports/P0-probe.md）。
