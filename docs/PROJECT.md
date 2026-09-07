# 杭麻 Bot 项目文档（多 Agent 协作版）

> 版本：2026-09-05 | 唯一竞技策略：**SpeedE**
> 服务器接入指南：v14（免认证：`GET /portal/api/guide?format=text`）

## 1. 项目目标与状态

杭州麻将（財神/白板=万能、自摸和、无荣和）竞技平台 AI。
- 已完成：全协议参赛 bot（多阶段锦标赛）、本地麻将引擎+模拟器、复盘拉取/重建/
  逐手审计流水线、测试房全自助（portal cookie 建房/关房）。
- 成绩（2026-09-04 正式赛 205 人）：rank 87/205（前半程协议 bug 致 0 胡拖累；
  修复后场均 +2.4）。已诊断修复 10+ 真机协议语义 bug（见 §5）。
- 现状：策略微调（SpeedB/E/F）经真机同桌 400+ 局验证**统计不可分**（SE≈0.5/场），
  收敛于平台——下一个突破方向在文档 §7。

## 2. 仓库结构

```
run_bot.py            参赛入口（--smoke / <token> [tid] --strategy speedE --log f）
bot/
  api.py              HTTP 传输（Bearer、全局令牌桶节流 12/s、429/网络退避）
  protocol.py         锦标赛主循环（多阶段状态机、跨轮 ready、404 瞬态重试）
  game.py             单场循环：事件驱动长轮询、快照权威、窗口去重/offer/守卫
  model.py            快照→view 转换、意图判定
  meldtrack.py        真机副露本地跟踪（e/g 累计、round 重置）
  speed.py            引擎父类 SpeedBase + 副露判据 SpeedCore（_want_claim 等）
  speede.py           SpeedE（唯一竞技策略）
  smoke.py            免认证冒烟（指南版本 + fan-calc 对拍）
mahjong/              纯规则引擎（tiles/hu/fan/shanten 精确/shanten_exact/sim）
arena/                本地自对弈评估台（runner/dashboard，默认 combo 见 §6）
tools/
  room_ctl.py         测试房自助（create/close；HM_PORTAL_COOKIE 环境变量）
  keep_alive.py       参赛看门狗（exit 0 自然停止）
  preflight.py        开赛前体检
  stability.py        稳定性矩阵（0 违规/守恒）
  replay_audit.py     本地日志 [audit] 决策 oracle 审计
tests/                100 测试（协议集成/引擎黄金集/策略）
logs/                 运行日志（--log 双写、bot_live.log）
var/replays/          正式赛复盘 JSON（10 场全量事件）
```

## 3. 协议要点速查（真机语义，勿用模拟器假设替代）

1. 快照 `my_hand` 恒为**不含刚摸牌**的 13-3e-g 张；本人摸牌只经
   `tile_drawn` 事件（tile 仅对自己可见，他人恒空）；game.py 按
   `expect=14-3e-g` 长度判断补第 14 张（副露后服务器部分路径已含摸）。
2. 快照**无 `offer_tile`**（窗口弃牌牌面只经 `tile_discarded` 事件公开）→
   game.py 维护 self_offer 注入；窗口去重键 = (phase, turn, offer_tile)。
3. 动作成功**不回退 seq=0**（保持水位挂起长轮询，否则收不到增量事件）；
   409/形态异常才重建。
4. 窗口响应 1s（chi/peng）——策略决策须 <100ms（SpeedE 单决策 ~2ms）；
   过慢会 409/被服务器代处理。
5. 每局结束（round_ended）：重置 tracker/river/self_drawn/self_offer。
6. 服务器约每 70-90 分钟重启一次（502→404 风暴）——404 重试 120s 再放弃。
7. 测试房每用户 1 活动房（close 释放）；M=1 房=四令牌真同桌无 AI。
8. 指南版本自检：`GUIDE_VERSION_KNOWN`（bot/__init__.py）。

## 4. SpeedE 决策（基准，改动需过 Arena+真机双验证）

1. 可胡即胡（含爆头摸白；纯速度，不做财飘/打点）；
2. 出牌：**弃后精确向听最小** → 听牌等待最多 → **孤张字牌优先** → 保留刚摸；
   抓打圈强制打刚摸；
3. 窗口：碰/直杠/吃仅当副露后成型更快（after<before，已听不碰）；
4. 自杠不做。

演进史：SpeedA（纯向听）→ SpeedB(+副露收益) → **SpeedE(+孤字 tie)**；
SpeedF（精确 ukeire 25ms）真机同桌 408 局与 E 统计不可分 → 不保留分支。
SpeedX1（tie 弃刚摸，2026-09-06）：本地 L1 WIN（1387 局 +2.2/场 CI 排除 0）→
真机同桌 200 场 δ+0.5 CI 含 0 → converged 不保留。第三次复现"本地衰减"结构
（B/A 本地胜 → 真机不可分）；SpeedX2（已见牌扣减）L1 1200 局 +0.2 不可分 → 不保留。
SpeedH（杠/链 EV 门控，2026-09-07）：自杠协议适配（P0 实测驱动）+ 门控候选实现，
**正式赛窗口 A/B 终裁 converged**（W1：150 场 δ+0.47/场 CI 含 0，150 局 0 杠触发）→
不晋级默认；策略实验分支移除（协议机器与审计工具链保留，见
docs/iter/reports/W1-speedh-window.md）。
迭代协议/统计口径/防重登记见 docs/自迭代方案.md + docs/iter/（真机 σ≈11 vs
本地 sim σ≈33 的校准已入档）。

## 5. 真机事故清单（已修复，回归勿破坏）

| # | Bug | 修复 |
|---|---|---|
| 1 | 快照 13 张→is_win 恒崩→0 胡 | tile_drawn 事件补第 14 张 |
| 2 | 动作后 seq=0 收不到增量事件 | 保持水位事件驱动 |
| 3 | 快照无 offer→窗口全 pass | tile_discarded 注入 offer |
| 4 | 副露后快照已含摸→重复注入 12 张 | expect 长度判断 |
| 5 | claim 后瞬时旧快照→长度冲突崩溃 | 形态守卫跳过本轮+decide 外层兜底 |
| 6 | tracker 跨局残留→整局废 | round_ended 全量重置 |
| 7 | 429 风暴（10 桌共享 16/s） | 进程级令牌桶 12/s |
| 8 | 窗口重复提交 409 死循环 | 窗口键含弃牌牌面+409 后标记已死 |
| 9 | 服务器重启 404 瞬态退出 | 404 重试 120s |
| 10 | 测试房跨轮 30min 空闲 void | registering 期周期 ready（30s） |

## 6. 验证流水线（每项改动照此执行）

```powershell
python -m unittest discover -s tests        # 100 测试（~2min）
python tools/stability.py                    # 0 违规/守恒矩阵
python -m arena.runner --combo "speedEx4" --games 200 --rounds 8   # 自对弈基线
# 真机（需 portal cookie 环境变量 HM_PORTAL_COOKIE）：
python tools/room_ctl.py create --m 1 --rounds 1    # 建房得 4 令牌
python run_bot.py <tok> --strategy speedE --log logs/x_青龙.log   # ×4 座
# 判定口径：同桌 ≥200 局，四席场均 SE≈0.7；E 双席互作对照；
# 单局分标准差 ~10 → 判差需局数 N>(2/δ)²·100（δ=期望差/场）
```

## 7. 下一突破方向（多 Agent 候选任务）

> 2026-09-06 迭代实况：§1/§2/§4/§5 均已实测收敛或受限（详见 docs/iter/）——
> **连续 4 代策略微调（E/F→x1/x2）收敛于平台，方向应转向评估方法学与对手模型**。

1. ~~tie 内"弃刚摸优先"变体~~（C001 已测：L1 WIN +2.2 → 真机 200 场 δ+0.5 converged）；
2. **防守维度**（speed 系全员抢胡无防守）：读取公开弃牌河算危险度、追听风险；
   view 的 river 已注入（game.py + sim 同口径）。**方法学限制**：防守收益需
   真防守对手才能体现，本地 L1/真机同桌（对手=自家 speed 系）会假阴性 →
   需先造"会防守的陪练"或正式赛实测（人工通道）；
3. **打点 EV 分支**：4 白板/爆头/财飘的高番取舍（规则 ×512 上限已入引擎）；
4. **短局口径**：WALL_RESERVE 已参数化（--wall-reserve）但**默认不翻 60**
   （reserve60 本地流局 71% 失真；旧复盘被 timeout 污染）→ 待干净真机统计校准；
5. ~~已见牌扣减~~（C002 已测：L1 1200 局 +0.2 不可分 → 该族封存）；
6. **评估方法学**（新方向，自迭代 R10 产出）：本地 sim 衰减偏差 > 2/场三次复现
   → 候选策略微调的期望收益已低于判定成本，除非引入对手模型/新规则环境；
   或转向**协议/稳定性域**（真机事故率、重启韧性）与**部署自动化**。MCTS 远期。 

## 8. 数据/凭据

- 门户 cookie：`HM_PORTAL_COOKIE=majiang_sid=...`（会话短命，过期问用户要新的）
- 复盘数据：`var/replays/t_dee58824c308/`（10 场 ×16 局，四家完整手牌可重建）
- 服务器：https://10.240.169.190:18080（caddy 自签 TLS，证书跳过）
