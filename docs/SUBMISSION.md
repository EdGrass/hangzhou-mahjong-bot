# 参赛程序说明（可直接粘贴到申报正文）

> 完整可运行源码：https://github.com/EdGrass/hangzhou-mahjong-bot

## 1. 程序是什么

杭州麻将竞技平台的**全自动对局程序**：以"向听数 + 真进张（live ukeire）"驱动的速度型
引擎为核心，配套 A/B 评测台、复盘审计与延迟基准工具链。

- 对局全程 **AI 自动决策，无任何人工干预**；
- 报名 → 到位 → 开赛 → 逐手决策 → 阶段切换 → 终态退出，**全流程无人值守**；
- 决策只使用**服务器公开状态 + 自己手牌**，不读取对手私有信息。

## 2. 运行环境与依赖

| 项 | 要求 |
|---|---|
| Python | **3.12**（实测 3.12.10；Windows / Linux 均可） |
| 第三方依赖 | **核心零依赖**——`run_bot.py` + `bot/` + `mahjong/` 只用标准库 |
| 可选依赖 | `fastapi` + `uvicorn`（仅本地自对弈看板 `arena/dashboard.py`，参赛不需要） |
| 硬件 | 普通 PC 即可（无 GPU、无数据库、无外部模型文件） |
| 网络 | 需能访问官方对战平台（自签 TLS，程序内部已处理证书校验） |

```bash
pip install -r requirements.txt   # 仅可选组件；参赛本身不需要装任何包
```

## 3. 如何接入官方平台

| 环节 | 实现 |
|---|---|
| 认证 | `Authorization: Bearer <参赛令牌>`；报名令牌自动发现赛事，全局令牌须显式给 tournament id |
| 状态机 | `registering → running → stage_done → stage_open → running … → finished`；自动报名 / 到位(ready) / 阶段出席确认 / 淘汰退出 |
| 事件驱动 | 走 **notify 事件流（SSE）**长轮询，不占用 `/state` 频率配额；事件合并后按需取快照 |
| 窗口应答 | 弃牌 3s、碰/吃 1s 窗口内提交决策；本机实测决策 **p99 ≈ 47ms**（远低于窗口预算） |
| 容错 | 429 / 5xx / 网络瞬断指数退避；**瞬态 404 容忍 120s 后重试**；窗口 409 竞态自动恢复；快照形态自适应（含/不含刚摸牌两种口径） |
| 自签 TLS | 内部使用不校验证书的 SSL context，无需额外配置 |
| 平台地址 | **不在源码硬编码**，用 `--server <URL>` 或环境变量 `HM_SERVER` 注入（地址由主办方提供） |

## 4. 如何启动

### 4.1 免认证自检（推荐第一步，不参赛）

```bash
python -X utf8 run_bot.py --smoke --server https://<平台主机>:<端口>
```

校验：服务器连通 → 接入指南版本（有未知 BREAKING 变更则报警）→ 番型计算接口语义
（13 张散牌必不胡 / 指南示例必胡且结算结构齐全）。不需要令牌。

### 4.2 参赛（最小命令）

```bash
python -X utf8 run_bot.py <参赛令牌> --server https://<平台主机>:<端口>
```

程序自动报名 → 到位 → 等开赛 → 逐局决策，赛完自动退出。

### 4.3 指定策略

```bash
python -X utf8 run_bot.py <参赛令牌> --server <URL> --strategy speedvalue
```

可用策略用 `python -X utf8 run_bot.py --help` 查看。

### 4.4 无人值守运行（推荐正式赛）

```bash
python -X utf8 tools/keep_alive.py <参赛令牌> --strategy speedvalue --server <URL>
```

阻塞式看护 `run_bot.py`：子进程异常退出（非 0）→ 5s 后自动重启，重试不设上限；
子进程自然结束（exit 0 = 终态/未晋级）→ 看门狗一并退出。看门狗自身不发网络请求，
避免与子进程争抢同一账号令牌。

### 4.5 开赛前一键体检

```bash
python -X utf8 tools/preflight.py --server <URL>
```

报告 `READY` / `NOT READY`（退出码 0 / 1）：版本一致性 + fan-calc 与本地引擎全字段对拍
+ 引擎单测。

### 4.6 环境变量方式注入平台地址

```bash
$env:HM_SERVER = "https://<平台主机>:<端口>"     # PowerShell
export HM_SERVER="https://<平台主机>:<端口>"     # bash
```

未指定时程序会以明确报错退出，不会静默连到错误地址。

## 5. 稳定性设计

- 事件用 **notify SSE** 驱动并做事件合并，避免并发下的限速风暴；
- 429 / 网络瞬断 / 5xx 指数退避重试；窗口 409 竞态自动恢复；
- **瞬态 404 容忍 120s**（服务器约每 70 分钟重启一次，会产生 502→404 风暴），
  持续超过 120s 才判定房间真删并退出；
- 决策延迟实测 **p99 ≈ 47ms**（窗口 1s / 3s，0 条超窗）；
- 长跑由 `tools/keep_alive.py` 看护，崩溃自动重启（报错/到位均幂等）。

## 6. 全自动决策说明

- 每一步（摸牌弃牌 / 碰 / 吃 / 杠 / 胡 / 过）均由程序自行决策并提交，**无人工干预**；
- 决策只使用**服务器公开状态 + 自己手牌**，不读取任何对手私有信息；
- 断线 / 窗口错过等情况由程序自身重试与重建状态，不需要人工介入。

## 7. 目录结构

```
run_bot.py    入口：令牌 / 策略 / 日志 / 复盘录制 / 自检
bot/          协议状态机、HTTP 客户端、策略引擎、窗口决策、notify
mahjong/      向听数、番型计算、规则模拟（纯标准库）
tools/        preflight 体检 / keep_alive 看门狗 / 复盘审计 / 延迟基准
arena/        本地自对弈与看板（可选）
tests/        单元测试
testdata/     fan-calc 黄金集（与平台口径对齐）
```

## 8. 复现与验证

```bash
python -X utf8 -m unittest discover -s tests          # 单元测试
python -X utf8 run_bot.py --smoke --server <URL>      # 与平台口径对拍（免令牌）
python -X utf8 tools/preflight.py --server <URL>      # 体检
```
