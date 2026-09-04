# 杭麻 SpeedA Bot（杭州麻将竞技平台）

以 **SpeedA**（向听数驱动的纯速度算法）为唯一参赛策略的 bot 工程。

## 快速开始

```powershell
# 免认证冒烟自检（服务器版本 + fan-calc 口径）
python run_bot.py --smoke

# 参赛（门户派发的参赛令牌；默认策略 speedA）
python tools/keep_alive.py <参赛令牌>            # 看门狗托管：自动重启+日志落盘
# 或直接： python run_bot.py <token>
# 全局令牌自测：python run_bot.py <token> <锦标赛id>

# 开赛前一键体检
python tools/preflight.py                        # READY 期望
```

## SpeedA 决策规则（bot/speed.py）

1. 可胡即胡（含爆头态——纯速度不打点绕路）；
2. 出牌 = 主键 **弃后精确向听数最小**（含财神/副露/七对，`mahjong/shanten_exact.py`），
   次键 = 听牌后**等待牌数最大化**（ukeire），同分偏好保留刚摸的牌；
3. 窗口：可直杠/碰会要；吃全过；抓打圈内只打刚摸的牌。

## 评估与优化（arena/）

```powershell
python -m arena.runner --combo "speedAx4" --games 200 --rounds 8      # 自对弈
python -m arena.runner --combo "speedBx2+speedAx2" --games 300 ...    # 变体对决
python -m uvicorn arena.dashboard:app --host 127.0.0.1 --port 8088    # 面板
python tools/stability.py                          # 稳定性矩阵（0 违规/守恒）
python -m unittest discover -s tests               # 全量测试
```

组合语法：`策略名x座数` 用 `+` 连接；新变体在 `arena/runner.py` 注册同名即可对打。
数据：`var/arena/{metrics.json, history.jsonl, games.jsonl}`（面板只读）。

## 结构

```
run_bot.py            参赛入口（--smoke / <token> [tid]，策略 speedA）
bot/                  协议层 + SpeedA（api/protocol/game/model/meldtrack/speed）
mahjong/              规则引擎 + 模拟器（tiles/hu/fan/shanten/shanten_exact/sim）
arena/                SpeedA 评估台（runner/dashboard）
tools/                keep_alive(看门狗) / preflight(体检) / stability(矩阵)
tests/                协议+引擎+SpeedA 测试（黄金集对齐 132/132）
docs/开赛操作单.md     开赛操作与异常决策树
logs/bot_live.log     参赛 bot 全程日志（看门狗落盘）
```

服务器接入指南版本追踪：`GET /portal/api/guide/version`（免认证），启动自检告警 BREAKING。
