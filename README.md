# 杭州麻将 AI Bot（hangzhou-mahjong-bot）

杭州麻将竞技平台的**全自动参赛程序**：报名 → 到位 → 开赛 → 逐手决策 → 阶段切换 →
终态退出，**全程 AI 自动出牌，无任何人工干预**。

核心引擎是"**向听数 + 真进张（live ukeire）**"驱动的速度型策略，配套 A/B 评测台、
复盘审计工具链、决策延迟基准与本地自对弈环境。

> 规则环境：杭州麻将（白板/财神为万能牌、自摸和、多家可和）。

---

## 1. 运行环境与依赖

| 项 | 要求 |
|---|---|
| Python | **3.12**（实测 3.12.10；Windows / Linux 均可） |
| 第三方依赖 | **核心零依赖**——`run_bot.py` + `bot/` + `mahjong/` 只用标准库 |
| 可选依赖 | `fastapi` + `uvicorn`（仅本地自对弈看板 `arena/dashboard.py`） |
| 硬件 | 普通 PC 即可（无 GPU、无数据库、无模型权重文件） |
| 网络 | 需能访问官方对战平台（自签 TLS，程序内部已处理证书校验） |

```bash
pip install -r requirements.txt     # 仅可选组件；参赛本身不需要装任何包
```

## 2. 快速开始

### 2.1 免认证自检（推荐第一步，不参赛）

```bash
python -X utf8 run_bot.py --smoke --server https://<平台主机>:<端口>
```

自检会校验 **服务器连通 → 接入指南版本（有未知 BREAKING 变更则报警）→ 番型计算接口语义
（2 个确定性用例：13 张散牌必不胡 / 指南示例必胡且结算结构齐全）**，全程不需要令牌。

需要"本地引擎 vs 平台 fan-calc 全字段对拍"时用 `tools/preflight.py`（见 §7）。

### 2.2 参赛（最小命令）

```bash
python -X utf8 run_bot.py <参赛令牌> --server https://<平台主机>:<端口>
```

程序自动完成 报名 → 到位(ready) → 等待开赛 → 逐局决策，赛事结束自动退出。

### 2.3 无人值守运行（推荐正式赛使用）

```bash
python -X utf8 tools/keep_alive.py <参赛令牌> --strategy speedc151 --server https://<平台主机>:<端口>
```

`keep_alive.py` 阻塞式看护 `run_bot.py`：子进程**异常退出**（非 0）→ 5s 后自动重启，
重试不设上限；子进程**自然结束**（exit 0 = 锦标赛终态/未晋级）→ 看门狗一并退出。
看门狗自身不做网络调用，避免与子进程争抢同一账号令牌。

### 2.4 指定策略 / 全局令牌 / 日志

```bash
python -X utf8 run_bot.py <令牌> --server <URL> --strategy speedc151   # 指定策略
python -X utf8 run_bot.py <全局令牌> <tournament_id> --server <URL>     # 全局令牌须带赛事 id
python -X utf8 run_bot.py <令牌> --server <URL> --log logs/run.log      # 日志双写落盘
```

### 2.5 平台地址注入方式

**平台地址不在源码中硬编码。** 二选一：

```bash
# 方式 A：命令行
python -X utf8 run_bot.py <令牌> --server https://<平台主机>:<端口>

# 方式 B：环境变量（PowerShell / bash）
$env:HM_SERVER = "https://<平台主机>:<端口>"     # PowerShell
export HM_SERVER="https://<平台主机>:<端口>"     # bash
```

未指定时程序会以明确的报错退出，而不会静默连到错误地址：

```
run_bot.py: error: 缺少平台地址：请用 --server https://<平台主机>:<端口>
               或设置环境变量 HM_SERVER（地址由主办方提供）
```

## 3. 如何接入官方平台

| 环节 | 实现 |
|---|---|
| **认证** | `Authorization: Bearer <参赛令牌>`（报名令牌自动发现赛事；全局令牌须显式给 tournament id） |
| **状态机** | `registering → running → stage_done → stage_open → running … → finished`，自动报名/到位/阶段出席确认/淘汰退出 |
| **事件驱动** | 走 **notify 事件流（SSE）**长轮询，不占用 `/state` 的频率配额；事件合并后按需取快照 |
| **窗口应答** | 弃牌 3s、碰/吃 1s 窗口内提交决策；本地实测决策 **p99 ≈ 47ms** |
| **容错** | 429 / 5xx / 网络瞬断指数退避；窗口 409 竞态自动恢复；快照形态自适应（含/不含刚摸牌两种口径） |
| **自签 TLS** | 内部使用不校验证书的 SSL context，无需额外配置 |

## 4. 决策引擎

每一步（胡 / 弃牌 / 碰 / 吃 / 杠 / 过）都由程序自行决策并提交：

1. **可胡即胡**（含爆头态，不做打点绕路）；
2. **弃牌** = 主键「弃后**精确向听数**最小」（`mahjong/shanten_exact.py`，含财神/副露/七对），
   次键「听牌后**真进张（live ukeire）最大**」（按可见牌扣除），同分偏好保留刚摸的牌；
3. **窗口（碰/吃/杠）** 仅在"副露后成型更快"时执行；抓打圈内强制打刚摸的牌。

决策只使用**服务器公开状态 + 自己手牌**，不读取任何对手私有信息。

## 5. 策略谱系（工程纪律：一切改动要过预登记判据）

```bash
python -X utf8 run_bot.py --help            # 查看全部可用策略名
```

| 类别 | 策略 | 状态 |
|---|---|---|
| **现役竞技臂** | `speedc151` | 基线/冠军臂，正式赛与测赛使用 |
| 挑战者（A/B 中） | `speedvalue` | 主端点 +1.97pp、z=1.16，**未过线**（判据 z≥1.50 且 80 房/臂） |
| 候选队列 | `speedgangtakec151fixed`（杠束）、`speedvaluepairdose`（对子剂量档） | 已预登记、冒烟通过，待排期 |
| 已否决（保留代码备案，勿重开） | `/state` 混用、缓存窗口决策 | 实测回退：决策年龄 744→3768ms；吃窗口 91/73 条 409 |
| 基础引擎 | `speedE` / `speedt…` / `speedc0xx` 系列 | 历史基线，用于回归对照 |

> 说明："候选编号越大"只代表**做得更晚**，不代表更强——任何候选必须以**单变量 A/B**
> 打赢现役臂并通过预登记判据才能采用。

## 6. 工程结构

```
run_bot.py         参赛入口（--smoke 自检 / 令牌参赛 / 策略选择 / 日志与复盘录制）
bot/
  api.py           HTTP 传输层（Bearer 认证、TLS、限速桶、429/网络退避）
  protocol.py      锦标赛主循环（多阶段状态机、跨轮 ready、瞬态 404 重试）
  game.py          单场循环（事件驱动长轮询、快照权威、窗口去重与守卫）
  model.py         快照 → 决策视图转换
  speed*.py        策略引擎与各代候选臂（现役 = speedc151.py）
  smoke.py         免认证自检（指南版本 + fan-calc 对拍）
mahjong/           纯规则引擎：牌/番型/胡牌/精确向听/模拟器（无外部依赖）
arena/             本地自对弈评测台（runner + 可选看板）
tools/             keep_alive 看门狗 / preflight 体检 / 复盘审计 / 延迟基准 / 机房工具
tests/             单元测试（协议集成 / 引擎黄金集 / 策略回归）
testdata/          fan-calc 黄金集（与平台口径对齐）
```

## 7. 测试

```bash
python -X utf8 -m unittest discover -s tests    # 全量单元测试
python -X utf8 tools/preflight.py --server https://<平台主机>:<端口>   # 开赛前一键体检
```

## 8. 说明

- 本仓库为**参赛作品源码**，不含任何账号令牌、Cookie 或平台地址配置（这些运行时注入）。
- 程序在对局中**不进行任何人工干预**，也不读取赛事之外的任何数据。
