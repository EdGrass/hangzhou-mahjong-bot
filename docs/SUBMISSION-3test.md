# 参赛程序说明（可直接粘贴到申报正文）

## 1. 程序是什么

杭州麻将竞技平台的**全自动对局程序**：以向听数/真进张驱动的速度型引擎为核心，配多档策略臂
（`speedc151` / `speedvalue` / 杠束 / 副露束等），并附带 A/B 评测、复盘审计与延迟基准工具。
对局全程 **AI 自动决策，无任何人工干预**。

## 2. 运行环境与依赖

| 项 | 要求 |
|---|---|
| Python | **3.12**（实测 3.12.10；Windows / Linux 均可） |
| 第三方依赖 | **核心零依赖**（`run_bot.py` + `bot/` + `mahjong/` 仅用标准库） |
| 可选依赖 | `fastapi` + `uvicorn`（仅本地自对弈看板 `arena/dashboard.py`，参赛不需要） |
| 网络 | 需能访问官方平台 `https://10.240.169.190:18080`（自签证书，程序内部已处理） |
| 硬件 | 普通 PC 即可（无 GPU、无数据库） |

## 3. 如何接入官方平台

- **协议**：`registering → running → stage_done → stage_open → running … → finished`；
  程序自动完成 **报名 / 到位(ready) / 每个阶段的出席确认**，开赛后自动进桌、自动出牌，阶段间隙自动等待，
  被淘汰或名单外自动退出，终态自动结束。
- **认证**：使用门户派发的**参赛令牌**（64 位十六进制字符串）。若用全局令牌，需再给一个 tournament id。
- **服务地址**：默认 `https://10.240.169.190:18080`，可用 `--server` 或环境变量 `HM_SERVER` 覆盖。

## 4. 如何启动

### 4.1 最简（单场全自动，推荐）
```bash
python -X utf8 run_bot.py <参赛令牌>
```
程序自行报名→到位→等待开赛→逐局决策，赛完自动退出。

### 4.2 指定策略
```bash
python -X utf8 run_bot.py <参赛令牌> --strategy speedc151
```

### 4.3 全局令牌 + 指定赛事
```bash
python -X utf8 run_bot.py <全局令牌> <tournament_id>
```

### 4.4 免认证自检（不参赛，验证环境与番型口径）
```bash
python -X utf8 run_bot.py --smoke
```

### 4.5 可选：带守护进程运行（长时间/多阶段更稳）
```bash
python -X utf8 runtime/_official_keepalive.py --strategy speedc151 --token-file <令牌文件>
```
它会在同账号独占校验通过后拉起 `run_bot`，异常退出时按退避自动重启。

## 5. 稳定性设计

- 事件用 **notify SSE** 驱动（不占 `/state` 频率配额）并做事件合并，避免 M=10 并发下的限速风暴；
- 429 / 网络瞬断 / 5xx 指数退避重试；响应窗口 409 竞态可自动恢复；
- 决策延迟实测 **p99≈47ms**（窗口 1s/3s，0 条超窗）；
- 自愈链：`_keeper`（监督 `match_super`）、`_watchdog`（卡死自愈，90s 巡检）、`_official_keepalive`（官方赛保活），
  Windows 计划任务入口 `_ensure_all.py`；官方赛期间用哨兵文件暂停测试房自愈，避免同账号并发（E002）。

## 6. 全自动决策说明

- 每一步（摸牌弃牌 / 碰 / 吃 / 杠 / 胡 / 过）均由程序自行决策并提交，**无人工干预**；
- 决策只使用**服务器公开状态 + 自己手牌**，不读取任何对手私有信息；
- 断线/窗口错过等情况由程序自身重试与重建状态，不需要人工介入。

## 7. 目录结构

```
run_bot.py    入口：令牌/策略/日志/复盘录制/自检
bot/          协议状态机、HTTP 客户端、策略引擎、窗口决策、notify
mahjong/      向听数、番型计算、规则模拟（纯标准库）
tools/        A/B 评测、复盘审计、延迟基准、机房工具
arena/        本地自对弈与看板（可选）
tests/        单元测试（23 个测试文件）
docs/         工程文档
runtime/      可选守护/保活/切换脚本
```

## 8. 复现与验证

```bash
# 单元测试
python -X utf8 -m unittest discover -s tests
# 与平台版本、番型口径对拍（免认证）
python -X utf8 run_bot.py --smoke
```
