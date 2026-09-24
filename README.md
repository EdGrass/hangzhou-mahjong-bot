# 杭州麻将竞技平台 Bot（Hangzhou Mahjong AI）

全程 **AI 自动决策**（出牌 / 碰 / 吃 / 杠 / 胡），**无人工干预**；直接接入官方对战平台参赛。

---

## 1. 环境依赖

- **Python 3.12**（Windows / Linux 均可；Windows 为当前实机验证环境）
- 依赖（见 `requirements.txt`）：

```powershell
python -m pip install -r requirements.txt
# 核心：numpy / torch / psutil
# fastapi / uvicorn 仅本地评估面板需要，不装也能参赛
```


> **模型文件（共 4 个）**：`speedvaluebc` / `speedc151bc` / `speedvaluemeld` / `speedvaluerank` / `speedvaluebcmeld` /
> **`speedvaluebaotouv5` / `speedvaluebcv` / `speedvaluebaotouvmeld` / `speedvaluebcvmeld`** 需要 `var/` 下的策略网络：
> `c073_orig_w2_net.pt`（BC 排序）· `c121_meld_net.pt`（学习副露）· `c089_ranker_net.pt`（教师排序器）· **`baotou_v1.pt`（爆头可达性 V）**。
> 这些文件**不在 `.gitignore` 的常规提交范围内**（`var/` 被忽略）⇒ 克隆后若缺失，相关臂会**静默退化为基线**。
> 仓库已用 `git add -f` 强制纳入**全部 4 个**模型；自检：
> `python -X utf8 var/_campaign_ready.py --arms speedvaluebc,speedvaluemeld,speedvaluerank`

## 2. 启动与平台接入

平台地址默认 `https://10.240.169.190:18080`（可用 `--server` 覆盖）。**令牌由平台派发**（报名令牌或参赛令牌）。

```powershell
# ⓪ 免认证自检（不参赛，只验证协议/规则/引擎口径）
python run_bot.py --smoke

# ① 直接参赛（推荐显式指定策略名，见 §3）
python run_bot.py <参赛令牌> --strategy speedvalue

# ② 看门狗托管参赛（自动重启 + 日志落盘，适合长时间比赛）
python tools/keep_alive.py <参赛令牌> --strategy speedvalue

# ③ 已有锦标赛 id 时（全局令牌自测）
python run_bot.py <全局令牌> <锦标赛id> --strategy speedvalue

# ④ 分阶段正式赛（推荐；自动完成 报名→到位→阶段确认→对局）
python -X utf8 var/_ready_1024.py --tid <TID> --token-file <TOK>                  # 到位确认（幂等）
python -X utf8 tools/tminus_check.py --strategy <ARM> --token-file <TOK> --tid <TID>   # 赛前总门禁
powershell -ExecutionPolicy Bypass -File var/_switch_to_official.ps1 -Strategy <ARM> -TokenFile <TOK> -TournamentId <TID>
# 赛后退场：python -X utf8 var/_exit_official.py
```

- 启动后 bot 自行**报名 → 到位 → 确认 → 自动对局**，全部动作由策略层产生，**无需任何人工输入**；
- 每局动作的提交延迟有硬性预算（实测 p50 ≈ 15ms、p99 < 50ms，远低于响应窗口）；
- 日志：`--log <file>` 双写；看门狗模式默认落 `logs/bot_live.log`（首次运行时自动创建）。

## 3. 策略（`--strategy <name>`）

`--strategy` 可取 `run_bot.py --help` 列出的任意已注册策略名；**当前生产策略以 `var/_keeper_strategy.txt` 为准**（逐役按预登记实验择优；撰写本 README 时为 `speedvalue`；**该文件与 `var/.official_spec.json` / `logs/` 均由程序运行时生成**，刚 clone 下来不存在属正常）
（V 加权出牌器：弃后精确向听最小 → 活进张/番/白板综合价值最大）。
`--strategy` **建议显式传**（不传时用代码内默认值，用途仅为兼容旧脚本）。

```powershell
python run_bot.py --help          # 查看全部可用策略名
```

## 4. 规则开关（重要）

平台每场可配 `YouCaiBiKao`（有财必考）。**上场前必须核对**：

```powershell
python tools/rules_guard.py --strategy speedvalue --token-file <令牌文件>
# 返回 0 = 策略与规则一致，可上场；2 = 不一致（禁止上场）；3 = 读不到
```

## 5. 开赛前一键体检

```powershell
python tools/preflight.py            # READY 期望（版本一致 / 规则口径 / 引擎单测 / 延迟）
python -m unittest discover -s tests # 全量测试
python tools/stability.py            # 稳定性矩阵（0 违规 / 守恒）
```

## 6. 目录结构

```
run_bot.py        参赛入口（--smoke / <token> [tid] / --strategy / --match）
bot/              协议层 + 策略层（api / protocol / game / model / meldtrack / speed* 系列）
mahjong/          规则引擎（tiles / hu / fan / shanten / shanten_exact / sim）
tools/            keep_alive（看门狗）/ preflight（体检）/ rules_guard（规则门禁）/ 各类审计
arena/            本地自对弈评估台（runner / dashboard）
tests/            协议 + 引擎 + 策略测试
docs/             操作手册与迭代记录（docs/iter/）
var/              运行时数据（令牌、日志、复盘缓存；不含任何密钥提交）
```

## 7. 设计要点（为什么这样接）

- **协议**：完全按官方门户接口实现（报名 / 到位 / 状态轮询 / 动作提交 / 心跳），并对 409、
  快照过期、响应窗口竞态做了自愈；
- **决策**：`bot/speed*.py` 一族策略共享同一套规则引擎口径（向听数、听牌、番计算与平台
  `fan-calc` 对齐，黄金集 132/132）；
- **只做 AI 决策**：不依赖人工点击，不读取外部输入，比赛期间仅使用平台公开信息。
