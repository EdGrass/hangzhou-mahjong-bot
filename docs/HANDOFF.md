# 交接 Prompt —— 杭麻 SpeedA Bot 项目（交接日期 2026-09-09 夜）

> 你是接手 `D:\hangzhouMaj`（杭州麻将竞技平台 AI Bot）的下一任 AI。本文件
> 浓缩了前一任的全部上下文、已验证事实、已排除方向与当前待决策项。请先完整
> 读完本文件，再读 `docs/PROJECT.md`、`docs/iter/reports/gap-full-picture-2026-09-09.md`。

## 0. 协作规则（用户级约束，最高优先级，见 ~/.dsh/AGENTS.md）

- **先商量方案、经用户明确确认后再动手改代码/文档**；只读操作（审查/查询/
  分析/汇报）不受限。用户回复"继续/可以/修吧/按你说的做"即视为确认。
- 用户是技术主导者，重视**真机证据**，讨厌"自我感觉良好的指标改进"。
  汇报时先给数据（复现命令 + 数字），不要粉饰，无效应如实说"排除"。
- 用户口头禅式指导："去自动房验证"、"继续"、"还是太差了"——意味继续推进。
- 平台级动作（正式赛报名、令牌轮换、策略默认切换）必须先请示。

## 1. 项目一句话

杭州麻将（自摸制、白板=财神万能牌、多高番）竞技平台 Bot；参加内网 AI
锦标赛，与外部顶级 bot（阿飞/陶康智能/卢本伟/Nomad/国士无双十三面听/赤木茂/
朱雀-5973/妈妈/八木仙/姚金毅/李兆坤…）在自动房与正式赛竞争。

- 我们的账号：`u_7a3fba48d70b`，**昵称当前为"EdGrass"**（曾用"貔貅-6837"，
  历史上 server 复盘里两种名字都会出现——按 uid 匹配，不要按名字）。
- 服务器：`https://10.240.169.190:18080`（自签证书，需 `ssl._create_unverified_context()`）。
- 指南版本：**v27**（`bot/__init__.py: GUIDE_VERSION_KNOWN = 27`，变更审计已做）。
- Python 3.12，所有脚本用 `python -X utf8` 运行。

## 2. 关键凭证与运行方式

- `var/.global_token`：全局令牌（**每次使用会轮换**，用于 `--match`/显式 tid/API 查询）。
- `var/.portal_cookie`：门户登录 cookie（**复盘/房间数据端点必需**，会过期需重取）。
- 启动自动房对局：
  - 单场：`python -X utf8 run_bot.py <tok> --match --strategy speedtm --log logs/x.log`
  - 监督循环（推荐）：`python -X utf8 tools/match_super.py --rooms 3 --strategy speedtm`
    （自动 预占房→显式 tid 跑→房终即时抓 ranking 归档 `var/auto_ranking.jsonl`）
  - **默认策略已切为 `speedtm`**（2026-09-09 用户批准）。
- 一房 = 10 场 × 8 局 = 80 局，约 15-30 分钟（看对手快慢）。

## 3. 代码结构速查

```
mahjong/        引擎：hu(胡判定/v21语义) fan(番) shanten_exact(精确向听,含
                god_meld 参数) shanten(waits) sim(自对弈引擎,含听牌/爆头统计)
bot/
  api.py        客户端(长轮询/SSE notify/match)
  game.py       play_game 主循环(协议适配核心：guard/offer注入/seq重建)
  model.py      snap_view(快照→策略 view，melds 服务器权威)、window_pending
  speed.py      SpeedCore：弃牌/窗口基础判据(_want_claim/_best_discard)
  speede.py     SpeedE ★历史基线（速度向听最小+孤字tie）
  speedm.py     +副露放宽(after<=before)         speedt.py  +tie弃牌偏好(拆对后置)
  speedtm.py    T+M ★当前默认                   speedq.py  七对路线锁定
  speedtqm.py   T+M+Q                          speedtp.py  T+M+碰严格(C017)
  speedu/v/k/w/wm/tk 等 = 历史候选(见§7)
tools/
  match_super.py     自动房监督循环(ranking 归档)
  gap_analysis.py    房 ranking 差距分析(--strategy 过滤)
  fetch_room_replays.py  批量拉服务器全信息复盘→var/replays/server/
  tenpai_race.py     听牌竞赛分析(听牌率/均听巡/爆头态率, --prefix 按房过滤)
  discard_profile.py 弃牌牌型画像      session_health.py 会话健康(409细目等)
  replay_oracle.py   复盘离线 oracle(任意座位重放对比)  stability.py sim 稳定性
  ab_balanced.py / replay_rec.py / replay_fetch.py / oracle_audit.py
tests/          unit tests（改引擎/策略后必跑：test_speed/test_speedt/
                test_protocol_integration/test_notify/test_engine_v21 等）
docs/PROJECT.md 事实基线   docs/iter/{queue.md,journal.md,reports/}
var/            运行时数据(gitignore)：令牌、replays、auto_ranking.jsonl、探针脚本
```

## 4. 必须知道的协议/数据事实（都是实测，别再重新踩坑）

1. **服务器快照（v24+）自带 `melds`（四家副露数组）与 `last_discard`**——
   副露以服务器 `melds[seat]` 为权威，本地 tracker 只兜底（自动房竞态下
   tracker 会分叉，曾致 guard 风暴 300-500 次/场，已修）。
2. **窗口 offer 缺失曾致副露被压 20×**：409/seq=0 重建路径下 tile_discarded
   事件会丢；已用快照 `last_discard` 兜底注入（`bot/game.py`）。
3. **SSE notify**（`/api/games/{id}/notify`）已接入，稳态 409 从 65+/分降到 ~0；
   `pass` 类 409 是无害噪音（服务器视同超时 pass），看 `session_health` 的
   `inv_harmful`（非 pass 409）才是真损失。
4. **复盘金矿**：`GET /portal/api/games/{gid}/events`（**带 cookie**）返回
   全信息复盘 `{blocks(start_hands 四家全手牌+全事件), rounds, seats(真名)}`；
   房间列表 `GET /portal/api/test-rooms/{room}`（带 cookie）。**自动房 ranking
   保留窗口很短**（房结束几分钟内），必须跑完即抓（match_super 已内置）。
5. 免 token 的 live 事件流里**对手摸牌 tile 不可见**（仅自己），但复盘全可见。
6. 场终批事件要在退出前喂 recorder（否则 round_ended 丢）；live 流近乎不推
   round_ended（逐局细分走复盘）。
7. v25：吃最多 2 摊（服务端校验，策略已自限）；v26 抓打圈豁免（低频未适配）；
   v27 门户榜（零影响）。

## 5. 方法论（血泪教训，务必遵守）

- **sim 只能验证"速度类"指标**（听牌率/听牌速度/胡率/合规）：sim 里平均番恒
  1.0-1.05（同质速度局无大番环境），**打点/爆头类策略 sim 无信号，只能真机**。
- **场分对照受房间强度严重混淆**：每房冠军随机（+0.6~+10.8/场），1-3 房场分
  不可判；**判定候选要看机制指标（听牌率/胡率/bao）+ 多房累计**。
- 真机候选验证标准流程：sim 合规（stability 零违规）→ 自动房 3 房
  （match_super）→ 拉复盘（fetch_room_replays）→ tenpai_race 逐房对比 +
  gap_analysis 场分 → 登记 queue.md/report。
- 历史"本地 A/B/自对弈场分"判据噪声巨大（σ≈33 sim）已弃用；改机制指标后
  多个候选效应才第一次可测。

## 6. 当前策略水平与差距（2026-09-09 真机复盘实测）

| 策略 | 自动房场分 | 听牌率 | 胡率 | 备注 |
|---|---|---|---|---|
| speedE（旧基线） | −2.47/场 | 31.5% | 13.1% | 880 席局 |
| **speedtm（当前默认）** | **−1.54/场** | **43.4%** | **20.8%** | 机制最优 |
| speedtp（C017 碰严格） | −0.91/场* | 41.2% | 20.8% | *冠军池偏弱，机制≈TM |
| speedtqm（+七对锁定） | −1.87/场 | 44.2% | 19.2% | Q 组件无效 |
| 顶级对手池 | +2.5~+10.8/场 | 60-72% | 25-46% | 番 1.3-1.72、爆头 21-44% |

**差距三层归因（已验证）**：
1. 表现层：听牌率差 ~20pp（冠军每 2/3 局听牌，我们不到一半）→ 胡率差 15pp；
   被截局已听率我们 28% vs 冠军 38-64%（我们多数局还没听就被胡）。
2. 决策层（根本）：我们一局做 30-40 次弃牌决策；现有 11 个候选**全是
   "单步贪心 + 手工判据"**（向听最小/有效牌/tie 偏好/白保留/七对锁定…）——
   单步最优 ≠ 整局听牌概率最大，30 步复利成 20pp。K1（+1 ply ukeire）只
   +3.6pp 证明"多算一步"不够 → 冠军用的是不同的决策算法（多步规划/学习）。
3. 番型层：我们 200+ 胡 0 爆头、fan 1.10；冠军爆头态到达率 8-16%（我们
   0.0%/1360 局）。爆头=副露 2-3 组+暗面子齐+白孤 或 6对+白 七对形，
   80% 起手有白——这是"现在牺牲一点速度换将来万能听"的多步规划问题，
   规则化尝试（W/WM/Q）全部失败。

## 7. 已排除方向（不要重复劳动，附证据）

| 方向 | 结论 | 证据 |
|---|---|---|
| 单步有效牌 tie（K1/speedu） | 无实质增益 | sim +3.6pp 听牌率、真机无差 |
| 副露频率（M mild） | 无效 | 真机 3 房 −2.13 vs E −2.47（噪声内）|
| tie 弃牌偏好（T） | 有效但量级小 | 听牌 +5pp sim；并入 TM |
| T+M（TM） | 当前最优 | 真机听牌 43.4%/胡率 20.8% |
| 白保留引擎约束（W/WM，god_meld=False） | **排除** | sim bao 0.62% 未迁移；真机 240 席局 bao 0 |
| 七对路线锁定（Q/TQM） | **排除** | 真机七对率 10.6% 未升、bao 0 |
| 碰/吃结构（C017 碰严格） | 机制≈TM | 场分 −0.91 系弱房 |
| T+K1 组合（TK） | 键序冲突不可叠 | sim 62.5% vs T 74% |
| MCTS/学习型 | **用户认为当前探索程度还不需要**（但规则空间已打穿，见§6.2）|

## 8. 待决策的下一步（前任已向用户提出，等用户选择）

跨过差距需要换决策算法，三条路径（工程量从小到大）：
1. **关键局面 rollout**：只在向听≤2 的弃牌上做 1-2 ply 采样前瞻
   （~200ms/决策，真机 3s 窗口可容纳）；先在 sim 用采样加速验证
   "多步视野值多少钱"。**最推荐先做**（轻、可证伪）。
2. **离线自对弈搜索/值迭代**：用现有 `mahjong/sim.py` 跑百万局，学一个
   "整局听牌概率/期望得分"评估函数替代向听主键。工程量中。
3. **冠军行为克隆**：`var/replays/server/` 已有 28000+ 顶级 bot 决策样本
   （含全手牌上下文），可监督学习弃牌模型。工程量中，数据现成。

## 9. 常用命令备忘

```powershell
# 跑自动房对照（后台）
python -X utf8 tools/match_super.py --rooms 3 --strategy speedtm
# 全量排名汇总 / 按策略过滤
python -X utf8 tools/gap_analysis.py [--strategy speedtp]
# 拉服务器复盘（房结束几分钟内！）
python -X utf8 tools/fetch_room_replays.py
# 听牌竞赛/爆头态分析（--prefix 用房 gid 前缀，注意完整前缀含前 2 字符）
python -X utf8 tools/tenpai_race.py --prefix "a_775f"
# sim 稳定性/听牌率回归
python -X utf8 tools/stability.py --strategy speedtm --seeds 6
# 单测（改引擎/策略后必跑）
python -X utf8 -m unittest tests.test_speed tests.test_speedt tests.test_protocol_integration
```
注意 PowerShell 引号易炸：复杂 python 一律写脚本文件到 `var/` 下再跑。

## 10. 立即该做的三件事（建议）

1. 读 `docs/iter/reports/gap-full-picture-2026-09-09.md`（全部数据与结论）
   + `docs/iter/queue.md`（候选队列与排除登记）。
2. `git log --oneline -30` 看最近改动（30+ 提交：协议修复/复盘打通/候选谱系）。
3. 向用户确认路径 1/2/3 的选择（前任最后停在这里），然后按 §5 流程推进，
   每一步先给方案再动手。
