# P1-speedh 报告 —— SpeedH（杠 EV 门控）实现与冒烟

> 日期：2026-09-07 | 状态：实现完成待窗口 A/B（P2）
> 设计：docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md
> 前置：P0 探针报告 docs/iter/reports/P0-probe.md（过胡合法；自杠被接受但需协议适配）

## 代码交付（分支 feat/speedh-window-ab）

| 提交 | 内容 |
|---|---|
| 12acca8 | T5b：game.py 自杠补牌形态适配（tile_drawn gang_replenish → 退补牌回 13-3e-g 决策） |
| 5a16e31 | 自杠当局快照 +1 全程容忍（round 级杠旗精确抽幻影） |
| 88267f7 | 幻影改本局集合式逐张移除（同局多杠不因单槽覆盖停摆） |
| b79a9ff | SpeedH 节流改局面指纹（409 重放才降级，不吞跨局面合法杠） |
| 1f4c266 | SpeedH decide 集成（胡优先/抓打不杠/补杠优先/暗杠/safe_gang 门控）+ run_bot 注册 |
| dbd9f9d/559ce38 | safe_gang 纯函数（严格长度纪律/None 哨兵/within_tolerance） |

语义：可胡即胡不变；杠仅在 safe_gang（结构安全、向听容忍内）时提交；白板禁杠；
409 同局面重放自动降级弃牌。speedh 已注册 run_bot（--strategy speedh），
未改默认 speedE。

## T6 真机短局冒烟（旧代码基线，房 t_11eb3256273a 已关）

- 2×speedh + 2×speedE 同桌 30 局：0 崩溃/0 Traceback/局次 100% 完成；
- speedh 座正常局与 speedE 行为一致（E 等价性稳定）；
- 1 次 draw 回合自杠（xuanwu 补杠 5b）：提交被接受 → 杠后补牌"退补牌 len=10
  expect=10 继续决策"生效（T5b 主路径 ✓）→ 正常弃 中 → 局次照常结算；
- 残余：该局后续 2 个自己回合出现旧守卫（len=11 expect=10 e=1 g=1 跳过）→
  5a16e31/88267f7 修复目标，待强制杠复验（t6b 房进行中）确认 0 守卫。

## 强制杠复验（t6b，进行中）

2×probe_gang（强制杠+无条件碰）+ recorder，观测：
- draw 回合自杠样本 ×N：杠后回合无"手牌形态暂不一致"守卫、正常续局；
- 观察项（非 SpeedH 路径）：probe 的窗口直杠+多重副露下出现过 len=expect+1
  守卫与 hu 409——判定为探针病理态（SpeedE 正常窗口判据不会高频直杠），
  记录不阻塞。

## 已知限制（v1）

1. safe_gang 向听容忍（GANG_TOL=2）与暗杠补牌语义按 P0 实测近似，窗口 A/B
   若胜出再按更多样本精调；
2. 杠后补牌事件的完整语义（直杠是否补牌等）仍以实测为准，当前实现覆盖
   draw 回合自杠（SpeedH 唯一新增路径）；
3. 强度结论未定：需 P2 正式赛窗口同赛段 A/B（两段式判定：快筛 n40-60 →
   终裁 n150，δ≥2/场 且 CI 排除 0 → WIN），运行手册 docs/iter/window-A-B运行手册.md。

## 下一步

t6b 复验收尾 → T10 总回归 + 最终评审 → merge 回 main → 等窗口令牌（用户）。
