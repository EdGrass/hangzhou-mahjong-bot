# 杭州麻将竞技平台 AI Bot（v8 协议骨架）

对接服务器接入指南 **v8**（2026-09-03，多阶段锦标赛协议 + 门户 description 新增）的
纯标准库 Python Bot。当前为**第一阶段骨架**：完整 v8 协议循环 + 示例策略验证链路；
真实牌技（胡牌判定 / 番型 / 出牌吃碰策略）为后续迭代，只改 `bot/strategy.py` 即可接入。

## 快速开始

```bash
# 免认证冒烟自检（版本自检 + fan-calc 番型口径往返校验，无需令牌）
python run_bot.py --smoke

# 正式运行（门户「测试房间」/「报名」派发的参赛令牌）
python run_bot.py <参赛令牌>

# 全局令牌（POST /api/users 注册所得）需显式带锦标赛 id
python run_bot.py <token> <锦标赛id>

# 其他服务器（默认 https://10.240.169.190:18080；本地调试可用 http://localhost:8080）
python run_bot.py <token> --server http://localhost:8080
# 或用环境变量 HM_SERVER 覆盖
```

运行前提：Windows 控制台已做 UTF-8 兜底（`bot/util.ensure_utf8`）；Python 3.10+ 即可。

## 目录结构

```
run_bot.py            CLI 入口：--smoke 冒烟 / <token> [tid] 完整协议循环
run_bots.py           四 AI 编排（4 子进程 + 席位日志 + 异常重启）
bot/
  api.py              HTTP 传输：Bearer、自签 TLS、429/网络瞬断退避、ApiError(status, body, code)
  model.py            牌码工具（1w-9w/1b-9b/1t-9t/东南西北中发白）+ 快照本人视角视图
  strategy.py         策略接口（Strategy） + NaiveStrategy（骨架期示例）
  game.py             单局循环：seq 长轮询、增量推进、seq=0 权威重建、窗口去重
  protocol.py         v8 锦标赛状态机：intent 映射（纯函数）+ 主循环
  smoke.py            --smoke 免认证冒烟
  util.py             日志与服务器地址
mahjong/              杭麻规则引擎（蓝图 M1，纯算法）：牌张编码 + 胡牌判定
                      （含财神百搭/七对）→ 后续：向听/听牌/番型/模拟器/Arena
tests/                unittest 离线单测（python -m unittest discover -s tests）
docs/杭麻AI蓝图-设计.md   牌技路线总设计（M1 引擎 → Arena 数据工厂 → 学习线）
```

## v8 状态机（进度真相 = GET /api/tournaments/{id} 的 status）

```
registering ──(报名+ready)──▶ running ──(晋级轮打完)──▶ stage_done ──(管理员推进)──▶ stage_open
                                                                                        │
stage_open ──(名单内 ready=出席确认；到点开赛)──▶ running ──▶ …（多阶段循环）              │
running(决赛轮打完) ──▶ finished       任时 ──▶ closed / void                             │
running 中断 ──▶ stage_done + stage_crashed=true（中断待重赛，继续轮询） ◀────────────────┘
```

关键语义（详见指南 §2.6，v7+ BREAKING）：

- **打完一个阶段 ≠ 结束**：空转窗口（active_games 为空）必须继续轮询直到
  `finished/closed/void`；
- **阶段确认不继承**：每个 `stage_open` 都要再提交 ready（名单外 409 `NOT_QUALIFIED`
  即已淘汰，退出）；确认幂等，主循环 10s 节流重复确认以覆盖崩溃重赛；
- **决赛加赛**：running 内新 game_id（含 `_s{k}`）自动出现，照常从
  `/api/me` 收割参赛；ranking 的 `games_played` 每阶段归零，不可跨阶段累计；
- 状态机映射集中在 `protocol.tournament_intent(t)`（纯函数，已单测）；
  未知 status 保守轮询不退出（版本前向兼容），配合 `bot/__init__.py` 的
  `GUIDE_VERSION_KNOWN`（当前 8）在入口做 BREAKING 自检告警。

## 策略接口（后续接入真实牌技的唯一接触面）

```python
class Strategy(ABC):
    def decide(self, view) -> dict | None: ...
```

- `view` = `model.snap_view(snapshot)`：本人视角，含 seat/phase/turn/
  responding_seats/drawn_tile/my_hand/god{baotou, chain_count, catch_play}；
- 返回动作 dict（`discard|chi|peng|gang|hu|pass`，格式同对局 API）或 None；
- 快照**无 allowed_actions**：动作合法性由策略自判，服务端纯验证，非法 409；
- 单局循环已处理：窗口「已响应」去重（(phase, seq) 签名）、动作后 seq=0 重建、
  增量事件补齐、409/网络/5xx 容错。

骨架期 `NaiveStrategy`：出第一张（抓打圈只出刚摸的）、窗口全过、不主动胡
（服务端可胡超时自动胡兜底——本策略秒回 discard，实际不触发）。

## 自测与迭代路径

1. `python -m unittest discover -s tests` —— 离线单测全绿；
2. `python run_bot.py --smoke` —— 免认证验证 连通/版本/番型口径 链路；
3. `python run_bot.py <测试房间令牌>` —— 端到端：报名→开赛→打牌→结算；
4. 后续牌技迭代：实现/替换 Strategy；协议层不动。
   建议同时用 `GET /api/test-rooms/{id}/games/{batch}/events`（免认证）离线拉取
   赛后完整事件流做算法优化（本骨架暂未内置，属迭代范围）。

## 本地评估：Arena 数据工厂 + FastAPI 训练面板（M2.5/M3.5 初版）

```powershell
# 1) 数据工厂：持续跑批次自对弈（默认 8 局×60 场/批，每 3s 一批）
python -m arena.runner --combo "heuristicAx4" --games 60 --rounds 8 --every 3
python -m arena.runner --combo "naivex2+heuristicAx2" --games 100 --rounds 8   # 单批

# 2) 训练面板（FastAPI，需 pip install fastapi uvicorn）
python -m uvicorn arena.dashboard:app --host 127.0.0.1 --port 8088
# 浏览器打开 http://127.0.0.1:8088 —— 总览/趋势/最近对局，3s 自动刷新

# 数据：var/arena/{metrics.json, history.jsonl, games.jsonl}（进程解耦，只读面板）
```

组合语法：`策略名x座数` 用 `+` 连接，如 `heuristicAx2+naivex2`；座位每局轮换，
成绩按策略身份聚合（混编中 heuristicA vs naive 直接可比：基准 100 局
heuristicA ≈ +9.8 均分 vs naive ≈ −9.8）。

## 版本追踪

服务器指南版本与变更日志：`GET /portal/api/guide/version`（免认证）。
本仓库按 v8 开发；服务器若出现更新的 BREAKING 变更，启动时会打 ⚠ 告警，
需人工核对 `bot/protocol.py` 与 `bot/game.py` 语义后再升级。
