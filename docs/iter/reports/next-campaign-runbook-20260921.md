# 下一役 Runbook（2026-09-21 立，供 09-23 判决落地后**机械执行**）

> 只备好、不执行。配套：`docs/预登记-三臂战役-20260922.md`（判据/闸门/阵容）、
> `docs/iter/reports/session-handoff-20260921.md`（本会话证据与 5 条撤回）。
> **红线**：绝不杀 `run_bot`；一账号一房；战役期间不改 `bot/` 热路径；重离线活只在**无对局的空档**跑。

## 0. 阵容（机械分支，不需要临场决定）

| 本役 `speedc151` 的 §11.3 判词 | 基线 | 候选 1 | 候选 2 |
|---|---|---|---|
| `adopt` / `adopt-early` | **`speedc151`** | **`speedc135d`** | **`speedc211`** |
| 其余（keep-baseline / futility / drop-arm） | **`speedtugc`** | **`speedc135d`** | **`speedc151b`**（= 有界 c151，见 §2） |

- `c135d` 过不了 M=10 门禁 ⇒ **换成 `speedc221`**（见 §3 判定表）。
- 阈值：三臂都按**单变量**（1.96）还是**组合臂**（1.50）由**预登记 §1** 的表声明；`c135d`/`c221` 都是**单变量**（唯一改动是弃牌并列判据）。

## 1. 步骤总览（**严格按这个顺序**，全部在**同一个空档**里做完）

```
① ab_ctl stop                （停本役驱动）
② 等最后一房自然跑完 + 确认无对局（进程 / 最新 replay 目录 / auto_ranking 尾部）
③ 注册新臂进 run_bot.py       （备份 → 纯新增两行 → 导入自检 → 官方冒烟）
④ M=10 并发门禁               （注册之后才能跑；c135d / c221 / 基线各一遍）
⑤ 真实 spawn 验证             （keeper 由 watchdog ≤90s 拉起，观察它真开一房并正常结束）
⑥ ab_ctl start 三臂           （阵容按 §0）
⑦ 启动后自检 + 12~20 房机制闸门
⑧ 监控节奏（harm guard / 覆盖率 / 100・150 房读数）
```

⚠ **为什么 ③ 必须在 ④ 之前**：`_concurrency_bench.py <strategy>` 只能按**注册名**取策略；
⚠ **但 R873 起这条限制已放宽**：两个工具都支持**点号路径**（`bot.speedc135d.SpeedC135D`）⇒ 可以**先跑冒烟 + M=10 门禁，全部通过再注册**；
只有**裸名**（如 `speedc135d`）才依然要求先注册。
⚠ **为什么 ④ 必须在"无对局"时跑**：10 线程重活会与在途 bot 抢 CPU（红线 §9.30 因此出过 4.4s 超窗）。

## 2. ③ 注册新臂（**唯一会碰 `run_bot.py` 的一步，只做纯新增**）

1. 先备份：`Copy-Item run_bot.py var\_run_bot.py.bak_<YYYYMMDD>`
2. 在 `STRATEGY_FACTORIES` 里**只加两行**（跟在 `speedc135` 附近）：
```python
    "speedc135d": lambda: __import__("bot.speedc135d", fromlist=["SpeedC135D"]).SpeedC135D(),
    "speedc221": lambda: __import__("bot.speedc221", fromlist=["SpeedC221"]).SpeedC221(),
    "speedc151b": lambda: __import__("bot.speedc151", fromlist=["SpeedC151"]).SpeedC151(name="speedc151b", budget_ms=40.0),
```
   ⚠ `speedc151b` = **有界 c151**（R783 实测：与无界 c151 在 599 条真实决策上**分歧 0 条**）⇒ 行为一致、只把"无限预算"变成"有界 + 干净回退"。
   **不要**去改 `speedc151` 本身的定义（本役正在用它）。
3. 导入自检（**不启进程**）：
```powershell
python -X utf8 -c "import run_bot; f=run_bot.STRATEGY_FACTORIES; print(len(f)); [f[n]() for n in ('speedc135d','speedc221')]; print('OK')"
```
4. 官方冒烟（每个新臂 25 个真机局面）：
```powershell
# ★ 三档一起跑（R873）。只跑第一条 = 只测到弃牌路径，副露门控/副露延迟**完全没被覆盖**；
#   且 R873 起支持**点号路径** ⇒ 注册之前就能冒烟。
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedc135d.SpeedC135D,bot.speedc221.SpeedC221 --n 25
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedc135d.SpeedC135D,bot.speedc221.SpeedC221 --n 25
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedc135d.SpeedC135D,bot.speedc221.SpeedC221 --n 25
```
   预期：各档都 ✅、退出码 0；**`window-live` 那档必须出现非 `pass` 动作**，否则说明副露分支根本没跑到。
⚠ R873 实测：默认 `--kind window` 的 82,917 条记录里 **96.3% 是 pass**（pass 79,843 / chi 1,634 / peng 1,398 / gang 42）⇒ 拿它给“副露门控类”候选背书 = **等于没测**。

## 3. ④ M=10 并发门禁（**必须在无对局的空档跑**）

```powershell
# 基线对照
python -X utf8 var/_concurrency_bench.py speedtugc   --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0
python -X utf8 var/_concurrency_bench.py speedtugc   --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
# 候选
python -X utf8 var/_concurrency_bench.py speedc135d  --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0
python -X utf8 var/_concurrency_bench.py speedc135d  --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py speedc221   --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
# ★ R873 新增：副露/荣和路径的延迟（R815 已证 40ms 预算**只覆盖弃牌路径**，副露路径实测 max 186ms）
python -X utf8 var/_concurrency_bench.py speedtugc   --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_concurrency_bench.py speedc135d  --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_concurrency_bench.py speedc221   --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
```

**判定表**（清单 §3 的预算：draw 0 次 >3s；window 0 次 >1s；M≤10 至少 n≥500，推荐 n≥2000）

| c135d 结果 | 动作 |
|---|---|
| **0 次超窗** | 用 `c135d` |
| 有超窗 | **换 `c221`**（`c221` 的 p95 贴基线，见 R773；若 `c221` 也超窗 ⇒ 退回基线并记录） |

📌 **R880 起门禁一律用固定语料**：`--from-file var/smoke_corpus_v1.jsonl`（**5718 条**，draw 2200 / late 900（river≥30 的重形态）/ window-live 2200 / claim 500，**sha256 d2c4602c1f69b48d**）。
为什么：原来是“按 mtime 取最近 80 个文件”，**每跑一房语料就整体位移** ⇒ 同一臂在不同时刻跑出的尾部**不可比**。
⚠ 固定语料**刻意更难**（含晚局重形态）⇒ 绝对值不会与旧语料一致（实测 c151 draw p50 13.7ms→22.9ms），这是有意的：**可比性在固定语料内部**。
⚠ 每次记录门禁结果**必须同时记下：语料 sha256、kind、n**（工具会自动在输出尾巴打印语料指纹）。

⚠ **R873 起流程可以（也应该）倒过来**：`arm_smoke` 与 `_concurrency_bench` 都支持**点号路径**（如 `bot.speedc135d.SpeedC135D`）⇒ **先跑冒烟与 M=10 门禁，全部过了再注册进 `run_bot.py`**（旧的“必须先注册”只对**裸名**成立）。
⚠ 且 `_concurrency_bench` 的样本是 `var/replays/**/*.dec.jsonl` 里 **按 mtime 取的最近 80 个文件**⇒ **每跑一房样本就变**：记录门禁结果时**必须同时记下 n 与 kind**，跨天/跨臂的数字**不可直接比**（R873（c135d 今日 fixtures p50 0.6ms vs 昨日 17ms））。

## 4. ⑤ 真实 spawn 验证（改完注册表**必须**做）

**机制说明**：本役已 stop ⇒ 驱动不在跑；此时拉起对局的是 **watchdog 的 keeper**
（`var/_keeper_strategy.txt` 里的生产策略，`_ensure_all.py` 每 5 分钟、watchdog ≤90s 拉起）。
keeper 走的正是 `python run_bot.py ...` 这条真实路径 ⇒ **它能正常开一房，就证明改过的 `run_bot.py` 可导入、可 spawn**。

1. 记下当前时间；等 watchdog/keeper 真的起一房（`Get-Process python` 出现新的 `match_super` + `run_bot`）；
2. 该房跑完后复查：`var/auto_ranking.jsonl` 尾部有对应记录、`status=finished`、无异常；
3. 结论写法："keeper 真实 spawn 导入的是改过的 `run_bot.py`，该房正常完成 ✅"。
   （若 keeper 未在 5 分钟内起房 ⇒ 不要继续，先查 `HangzhouMajAutoHeal` 的 LastTaskResult 与 `var/_ensure_all.py` 日志。）

## 5. ⑥ 启动三臂战役

```powershell
# 例：基线=speedtugc 分支（c151 未采用）
python -X utf8 tools/ab_ctl.py start speedtugc,speedc135d,speedc151b 1 --bundles=speedc151b
# 例：基线=speedc151 分支（c151 被采用）
python -X utf8 tools/ab_ctl.py start speedc151,speedc135d,speedc211 1 --bundles=speedc211
```
> ⚠ **【2026-09-21 R801 修正：`--bundles=` 不可省】** 原命令漏了这个参数 ⇒ 实测
> `parse_start_args` + `build_cfg` 会得到 `bundles=[]` ⇒ **读表与采用工具把三个臂全当成"单变量"（阈值 1.96 / 终点 100 房）**，
> 而 `speedc151b`（c150 六机制束 + 多对子惩罚）与 `speedc211`（c152 − C136）**都是组合臂**（阈值 1.50 / 终点 150 房）。
> `build_cfg` 的 docstring 自己就写着这个坑："**一旦丢掉这个字段 …… 用更严的阈值 ⇒ 战役白跑**（2026-09-16 实测）"。
> **正确的臂类型**：`speedc135d` = **单变量**（唯一改动 = `s≥1` 用有界真进张）；`speedc151b` / `speedc211` = **组合臂**。
- `rooms=1`（一账号一房，E002）；
- 三臂按轮转排批；`--bundles=` 留空（三臂都按单变量阈值 1.96）；
- ⚠ **基线必须写在第一位**（`ab_ctl` 用它当 base）。

## 6. ⑦ 启动后自检 + 12~20 房机制闸门

| 检查 | 命令 | 通过标准 |
|---|---|---|
| 配置 | `Get-Content var\.ab_mode` | `arms` 三个、`started` 是当下 |
| 驱动 | `Get-Content var\_ab_driver.out -Tail 1` | 有"已排批 arm=..." |
| 进程 | `Get-Process python` | watchdog/prod_monitor/_ab_driver/match_super/run_bot 齐 |
| 归属 | `python -X utf8 var/_verdict_validity.py` | 每臂并行覆盖 ≥60% |
| 熔断 | `Get-Content var\_ab_driver.out` 搜"熔断/异常" | 无 |
| **机制** | `python -X utf8 var/_offline_compliance.py --strategies speedtugc,speedc135d,speedc151 --n 400` | 候选合规率应 ≈ 离线预测（c135d 99.9% / c151 95%）→ 说明**真的在按新判据打** |
| **慢漏看护** | `python -X utf8 var/_harm_guard.py` | 退出码 0（未触发）；非 0 时按预登记处置 |

## 7. ⑧ 监控节奏

| 时点 | 动作 |
|---|---|
| 每批（~15min） | `_harm_guard.py`（慢漏） |
| 12~20 房/臂 | 机制签名闸门（§6 表最后两行） |
| 50 房/臂 | 中期读数（`ab_readout` + 三轴） |
| **100 房/臂** | 完整读数 + **非劣性/临时采用判定**（预登记 §2.2/§2.2-bis） |
| **150 房/臂** | 终判（`ab_adopt.py <候选> --dry-run`） |

## 8. 回滚（任意时刻）

```powershell
python -X utf8 tools/ab_ctl.py stop     # 停驱动；watchdog ≤90s 把 keeper 拉回（基线/生产策略）
```
- `stop` 会把生产恢复成 `_keeper_strategy.txt` 里的策略；**若要留在新策略上，必须显式改 `_keeper_strategy.txt` + `.official_spec.json`**（清单 §4 的切换步骤）。
- 注册表回滚：`Copy-Item var\_run_bot.py.bak_<YYYYMMDD> run_bot.py -Force`（**只在无对局时做**）。
- ⚠ **绝不**手动跑 `var/_rotate_token.py`。

## 9. 本 runbook **不做**的事

- 不改本役任何判据/时间表（本役到 150 房为止照旧）；
- 不动 `bot/` 热路径（只新增 `bot/speedc135d.py`、`bot/speedc221.py` 两个文件，它们早已存在）；
- 不在有对局时跑门禁；不在有对局时改 `run_bot.py`。

### 3-bis 【2026-09-21 12:0x R786】**M=10 门禁必须加"行为分歧率"这一列**（否则门禁会假阳性）

**为什么**：`_concurrency_bench.py` 只报延迟。**预算臂在 M=10 下会大量回退到基线**（墙钟预算 vs GIL 争用），
而回退后的延迟**更好看** ⇒ 单看延迟，一个"实际已退化成基线"的臂会**通过门禁**。

**必过项（两个都要）**：

| 项 | 判据 | 做法 |
|---|---|---|
| 延迟（原有） | draw 0 次 >3s；window 0 次 >1s；n≥500 | `var/_concurrency_bench.py <臂> --threads 10 --per-thread 200 --warm 0 [--kind window]` |
| **行为分歧率（新增，必过）** | **≤5%** | `var/_m10_divergence.py`：同一批视图先单线程算参考动作，再 M=10 并发算一遍，逐条比对 `(action,tile)` |

- 若分歧率 > 5% ⇒ 该臂**在比赛里等于没带机制** ⇒ 换"**确定性工作量上限版**"（只对最小向听组前 K 个候选取真进张，K=2~3），或退回基线。
- 适用臂：`speedc135d`（40ms 墙钟预算）、`speedc151b`（40ms 墙钟预算）。
- ⚠ 本条是**推算**（R786 ①-③），必须由 T-6h 的这次实测**确认或否证**。
> ⚠ **【2026-09-21 12:0x R787 更正】本节的量级已下调**：R786 把 M=10 的墙钟膨胀估成 ~×10，但
> **项目 09-17 二测（真实 M=10）的 draw p99 = 84.6ms** vs 我们单线程 p99 ≈80ms ⇒ **真实膨胀只有 ~1.1 倍**。
> ⇒ **"行为分歧率"仍建议加**（唯一能"知道"的办法，成本极低），但**不再是"臂会在比赛里消失"的紧急项**。

### 3-ter 【2026-09-21 12:5x R799】**维护窗口：T-6h 门禁到底怎么跑？**（原 runbook 假设了一个不存在的空档）

**先说清事实（本轮实测）**：
- 平台 `GET /portal/api/features` → **`match_enabled = True`**；
- `var/_feature_mode.py` 的 `handle_pause_on_startup()`：**只要平台 `match_enabled=True`，`.pause_mode` 会被自动删除** ⇒
  **`.pause_mode` 是"平台宕机时冻结"用的，不能当维护窗口**；
- `ab_ctl stop` 会**删掉 `.ab_mode`** ⇒ `_ensure_all.py`（计划任务 `HangzhouMajAutoHeal`，每 5 分钟）随后走"正常"分支
  ⇒ **会重新拉起 keeper** ⇒ **空档只有"stop 到 keeper 起来"这段（watchdog ≤90s）**，对跑一次 M=10 门禁**太短**。
⇒ **结论：目前没有任何内建手段能"把无对局窗口按住"。**

#### 正确流程（**会让生产暂停，执行前必须确认；第 5 步漏做 = 生产静默停摆**）

```powershell
# 0) 前置：确认没有在途房（等当前房自然跑完；绝不在对局中杀 run_bot）
Get-Process python | Select-Object Id,StartTime
Get-Content var\_ab_driver.out -Tail 1

# 1) 冻结自愈链（这是唯一可靠的办法；可逆，务必记住要恢复）
schtasks /change /tn HangzhouMajAutoHeal /disable
schtasks /query /tn HangzhouMajAutoHeal /fo LIST | Select-String Status     # 期望 Disabled

# 2) 停生产者（顺序：先停 A/B 驱动，再停 keeper/match_super）
python -X utf8 tools/ab_ctl.py stop
# 确认没有 match_super / run_bot 残留（有残留就先等它自然结束，不要杀）

# 3) 跑 T-6h 门禁（延迟 + R786 新增的"行为分歧率"列）
python -X utf8 var/_concurrency_bench.py <臂> --threads 10 --per-thread 200 --warm 0
python -X utf8 var/_concurrency_bench.py <臂> --threads 10 --per-thread 200 --warm 0 --kind window

# 4) ★ 恢复自愈链（**漏做这一步 = 生产静默停摆**）
schtasks /change /tn HangzhouMajAutoHeal /enable
schtasks /query /tn HangzhouMajAutoHeal /fo LIST | Select-String "Status|Next Run"   # 期望 Ready + 未来时间
```

#### ★ 交叉引用（R800）：T-1h 的**切换脚本**与 T-6h 的门禁**共用同一个前置条件**

`var/_switch_to_official.ps1` 自带 `-DryRun`，本轮已干跑验证（**零副作用**），并且**它自己会拒绝在有对局时继续**：

- 干跑输出里明确打印：`仍有对局/监督进程：run_bot=1 match_super=1 —— 请等其自然结束后重跑本脚本`，
  以及 `_ab_driver 仍在跑 … 若超过 25 分钟仍在 ⇒ 必须人工确认后再起正式赛（否则 E002）`（对应退出码 2/3）；
- ⇒ **它和 T-6h 门禁一样，要求"无对局 + 无驱动"**。

**⇒ 因此：§3-ter 的"维护窗口"流程是 T-6h 门禁与 T-1h 切换的公共前置步骤**，不要分别临场想办法。
顺序建议：**同一个窗口里先后做完** = 冻结自愈链 → 停驱动/keeper → 跑 T-6h 门禁 → `var/_switch_to_official.ps1`（先 `-DryRun`，再真跑）→ **恢复自愈链**。

#### ✅ 步骤 1 与 5 已实测（R803，2026-09-21）——本条**取代** R799 的"未实测"标注

三条证据（**全部零生产风险**跑出来的）：

1. **假任务全链路**：新建探针任务 `HangzhouMajDryRunProbe`
   → `schtasks /change /tn … /disable` ⇒ 查询得 **`Status: Disabled`**
   → `schtasks /change /tn … /enable` ⇒ 查询得 **`Status: Ready` + 未来 `Next Run Time`**
   → 删除探针。**往返全程无报错**。
2. **真实任务的 `/change` 权限**：对**真实任务** `HangzhouMajAutoHeal` 执行**幂等** `/change /enable`（它本来就 Enabled ⇒ no-op），返回
   `SUCCESS: The parameters of scheduled task "HangzhouMajAutoHeal" have been changed.`；
   且变更后 `Status: Ready` / `Next Run Time` / `Last Result: 0` **三者均未变化**
   ⇒ **我们对这个任务确实有 `/change` 权限**（这条已从"猜测"升级为"实测"）。
3. `schtasks /query /tn HangzhouMajAutoHeal /fo LIST /v` 显示 **`Logon Mode: Interactive only`**、**`Run As User: caiyuxin05`**
   ⇒ `/change` **不会索要密码** —— 这是"权限/策略错误"最可能的来源，**现已排除**。

- ⚠ **唯一仍未被证明的一条**：`/disable` 之后自愈链**确实不再拉起 keeper**（即"冻结真的生效"）。
  这条**只能在真正的维护窗口里被证明** ⇒ 到点**必须**在 `/disable` 后亲眼确认 `Status: Disabled` 再往下走。
- ⚠ **步骤 5 仍是全流程唯一"漏做即生产静默停摆"的一步**（`/enable` 漏做 ⇒ watchdog 不再自愈）。

#### 退路（**保留备用**，已不再是预期路径）
若到点**仍**出现权限/策略错误：
① 只做步骤 2（停生产者）＋接受 **watchdog ≤90s** 的窗口，**先跑 `--kind window` 那一半**（更短）；
② 再用 **4 线程**跑 draw 那一半，并在报告里注明"**非正式门禁**"。

#### 若不想冻结生产（替代方案，**不是**正式门禁）
- **降并发筛一遍**（4 线程 × 100）**只能在战役期间做**，且必须注明"这是筛查、不是正式门禁"；
  它的价值是抓**数量级**的延迟/行为异常（例如某臂 p99 飙到秒级），不能替代 10 线程的正式结论。
- ⚠ 绝不在有对局时跑 10 线程门禁（红线 §9.30：曾造成 4.4s 超窗）。

---

## §10 判决读出清单（R818~R822 更新，2026-09-21）

### §10.1 到点必跑（100 房 / 150 房，按此顺序）

> **✅ R956（已完成）**：本役窗口的**门户复盘补抓已提前做完** —— 覆盖 **109/109（100%，缺 0）**，新增 180 文件、失败 0、耗时 5.1 分钟。
> ⇒ **到点可跳过本步**，直接从判据类工具开始（省 ~5~17 分钟）。
> （工具 docstring 估的“一房 ~80 请求”偏悲观；实测是 18 房 × 10 局 = 180 个文件 / 5.1 分钟。）


```powershell
# ⚠ --since 一律用**空格**形式（把 .ab_mode 的 started 原样粘进来）。
#   写成 ISO 的 "2026-09-20T14:54:07" 会静默丢掉整个第一天（R871；已在 tools/ 里归一化，但别再教坏自己）。
python -X utf8 tools/ab_readout.py --since "2026-09-20 14:54:07"   # ← 本役实际值
python -X utf8 var/_first_rate_readout.py --since "2026-09-20 14:54:07"   # ★ 第一率差值 + z（见 §10.14 口径提醒）
python -X utf8 var/_power_two_endpoints.py --since "<本役 started>"    # ★ 功率表（60/100/150）
python -X utf8 var/_tenpai_by_arm.py --since "<本役 started>"
python -X utf8 var/_improve_rate.py --rooms 120                        # 向听前进率（成型轴）
python -X utf8 var/_ukeire_width.py --rooms 120 --per-role 600         # 1 向听宽度（成型轴）
python -X utf8 var/_wait_quality.py                                    # 听牌活等张 / 听牌后胡率（慢，~17 min，Idle）
python -X utf8 var/_camp_integrity.py                                  # 混臂 / 半房 / games
```

### §10.2 ★ 记号约定（2026-09-21 统一，**别再读错**）

- `ab_readout.py` 打印的 `b − a = … **±** …` 里的 `±` 是 **95% CI 半宽（≈1.96×SE）**，**不是 SE**；
  **SE = ± / 1.96**，`t = diff / SE`。
- 新增工具一律**明写 `SE=`**（`_first_rate_readout.py`、`_power_two_endpoints.py`）。
- ⇒ 看到 `±` 先问是哪件工具；**跨工具比"分辨率"时一律换算到 SE。**

### §10.3 ★ 功率表（t=1.5 的最小可测差；SD 为本役实测）

| 房/臂 | 净分 MDE（净胜/房） | 第一率 MDE |
|---:|---:|---:|
| 60 | ±50.8 | ±9.3pp |
| **100（建议）** | ±39.4 | **±7.2pp** |
| 150 | ±32.2（= 原始分 ±24.2） | ±5.9pp |

⇒ 若以**第一率**为准：**100 房/臂是性价比点**（相对 150 省 1/3 时间，仍能判出当前量级的效应）。

### §10.4 下一役两条分支（**阵型待用户裁决；下面两行是可直接执行的**）

| 分支 | 启动命令（**`--bundles=` 不可省**） | 准备状态 |
|---|---|---|
| c151 **未采纳** | `python -X utf8 tools/ab_ctl.py start speedtugc,speedc135d,speedc142 1 --bundles=speedc142` | **零准备**（三臂全已注册；`test_speedc142` 6/6 OK） |
| c151 **采纳** | `python -X utf8 tools/ab_ctl.py start speedc151,speedc135d,c151m2 1 --bundles=c151m2` | 需先注册 `c151m2` **一行**（见 §10.5） |

- `speedc135d` 位：**保留**（被三条独立证据强化：真机成型 **+2.0pp**、1 向听 live 更窄 −2.1、前进率 −5.2pp）
- ⚠ **不要注册 `speedc151b`** —— 它与**早已注册**的 `speedc187`（有硬时限的 c151，预算 100ms）是**同一构造**，
  实测对 c151 都是 **0 分歧**（R821）。需要"有界 c151"时**直接用 `speedc187`**。

### §10.5 注册 `c151m2`（**只在本役结束后做**；战役期间禁止改 `run_bot.py`）

在 `run_bot.py` 的 `STRATEGY_FACTORIES` 里、`"speedc151"` 那一行之后插入**一行**：

```python
    # C151M：c151 + 副露门控档位放宽（K=2 ⇒ 目标带；K=0 与 speedc151 逐例等价）
    "c151m2": lambda: __import__("bot.speedc151m", fromlist=["SpeedC151M"]).SpeedC151M(mild_upto=2),
```

插入后**必须**：
1. `python -X utf8 -c "import sys; sys.path.insert(0,'.'); import run_bot; print('c151m2' in run_bot.STRATEGY_FACTORIES)"` ⇒ 期望 `True`；
2. `python -X utf8 tools/arm_smoke.py --kind window-live --class bot.speedc151m.SpeedC151M --n 25` ⇒ 冒烟；
3. **真实 spawn 验证**：`python -X utf8 run_bot.py --strategy c151m2 --help` 级别的启动检查 + 一房实跑；
4. **T-6h 的 M=10 门禁**（§3-ter 维护窗口）必须跑 `c151m2`，**不能因为"它设了 40ms 预算"就跳过**
   —— R815 已证 **40ms 只覆盖弃牌路径、不覆盖副露路径**（实测 max 186ms ≫ 40ms）。

### §10.6 ★ 下一役期间的硬要求（R807 / R822）

- **机器必须保持空闲**：`budget_ms` 到期即回退基线 ⇒ 机器被加载时**候选的实际生效量被稀释**；
  R807 实测 20ms 处已有 **1.33% 自相矛盾**，40ms 起在 idle 下为 **0%**；
- 本会话所有重离线活一律走 `_lowprio`（Idle 优先级）—— **到点也照此办理**；
- R822 另证：**40ms 预算从未截断**（20ms→无界，截断率全 0%、Δlive 完全一致）⇒ 主杠杆 `c135d` 足额生效。
### §10.7 ★ 门禁的**数据前置步骤**（runbook 补漏，2026-09-21 R834）

> **来源**：本役预登记 `docs/预登记-三臂战役-20260920.md` **§3.1「闸门固定跑法」**（原文写着"直接照抄"）。
> **本次核对发现 runbook §10.1 漏掉了这三步** —— 而 §3.1 的原文警告过：
> **"干跑发现战役期间没有任何东西在抓门户复盘 ⇒ 覆盖率类闸门会读到 0 房"**。

**到点必须先跑（顺序不可颠倒）：**

```powershell
# ① ★ 先补门户复盘（覆盖率口径必须走门户；不跑这步会读到 0 房 / 陈旧数据）
python -X utf8 tools/fetch_room_replays.py --since "<本役 started>" --rooms 120 --gap 0.4

# ② c151 的对子签名闸门（本地 dec 即可，不需门户）
python -X utf8 tools/pair_signature.py --since "<本役 started>"
#   判据：c151 的「>=2 对占比」须明显低于基线

# ③ 机制构成核对（杠/爆头/财飘/七对；需要 ① 的数据）
python -X utf8 tools/mech_mix.py --arms speedtugc,speedc151 --since "<本役 started>"
#   读法：c150/c147 这类束要让「杠/轮、财飘%、爆头%」明显高于基线臂；
#         若这些没动 ⇒ 干预没生效，应停臂而不是等分数
```

**§10.7.1 实测（2026-09-21 14:2x，本役 44 房/臂）**

| 步骤 | 结果 |
|---|---|
| ① `fetch_room_replays` | **EXIT=0；新增 170 局、失败 0、跳过已存在 740** ⇒ **门户复盘覆盖 87.1% → 98.9%** |
| ② `pair_signature` | `speedc151` **≥2对占比 62.1%** vs `speedtugc` **70.7%** ⇒ **−8.6pp，门禁通过** |
| ③ `mech_mix` | `speedc151` **杠/轮 0.0568**（明杠 10 / 暗杠 5 / 补杠 5）vs 基线 **0.0000** ⇒ **杠干预生效** |

- 新增纪律（同 §3.1）：**任何"到点必须跑"的闸门，开跑当天就要用 1~2 房样本干跑一遍**，
  确认它真的出数 —— 本次正是靠这条发现了"覆盖率闸门读不出来 / 门户没抓"两个坑。
- ⚠ `mech_mix` 的 `爆头%`（c151 21.8 vs 基线 34.2）与 `均番`（1.24 vs 1.41）**只有 4 房** ⇒ **噪声极大，只作观察**。
### §10.8 ★ 熔断预警与响应（2026-09-21 R837/R838）

> **背景**：`_ab_driver.py` 自带熔断 —— **快档 k=6 房、阈值 −300**；**慢档 k=12 房、阈值 −150**
> （差值 = 候选近 k 房均值 − 基线同期近 k 房均值）。
> 一旦触发 ⇒ **"终止 A/B，回退基线 `speedtugc`"** ⇒ **本役数据作废**；
> 先例：**09-20 14:43:08 熔断 → 14:54:07 重启**（代价 ≈ 已积累的 ~1 天）。

**每轮巡检查一次：**

```powershell
python -X utf8 var/_breaker_watch.py     # 只读复刻，打印当前 6/12 房差值与"离阈值多远"
```

**2026-09-21 14:37 实测**：候选臂 n=44 ⇒ **快档差值 −49.3（余量 +250.7，OK）**、
**慢档差值 +38.8（余量 +188.8，OK）** ⇒ **离熔断都很远。**

**若真的触发（响应三步，机械照做）：**

1. **记录**触发时的 **6 房 / 12 房窗口读数**（`_breaker_watch.py` 立即跑一次）+ `_ab_driver.out` 里的熔断原文；
2. **写明定性**：**"这是熔断兜底触发，不是预登记判决"** —— 真正的判决是终点 **t 检验**（§11.3）；
3. **按先例重启同一战役**并记录理由（`ab_ctl.py start … --bundles=…`，注意 `--bundles=` 不可省）。

⚠ **不得在本役进行中调整熔断阈值**（§4 是预登记条款）；**R837 已量化慢档对"零效应臂"的单窗误触发率 2.9%**
⇒ 若想改进（例如慢档 −150 → −250），**只能写进下一份预登记**。
### §10.9 ★ 机制读出补充（2026-09-21 14:5x，R842~R845 新增）

> R811~R845 把"缺口在哪"收敛到了一个**很锐的形态**：**不是均值，而是窄尾**。
> 下面四条是产出这些结论的仪表，**100/150 房门禁应一并重跑**（看下一批臂有没有移动这些量）。

```powershell
# ① 按巡分层的 1 向听宽度（含"窄尾"比例 P(live<=14)）
python -X utf8 var/_ukeire_width.py --rooms 120 --per-role 600

# ② 共同起点 + 固定窗口的前进率（消掉"哪些手还留着"的筛选）
python -X utf8 var/_advance_from_common_origin.py --rooms 300 --k0 4 --k1 7
#   口径：第 4 次弃牌时向听 == s0 ⇒ 第 7 次弃牌时是否已到 0 向听

# ③ 1 向听手牌的形态（对子/字牌/白/孤张/副露，按臂）
python -X utf8 var/_shanten1_shape.py --rooms 400

# ④ 死等审计（真进张族在 0 向听的语义盲区，逐策略重放）
python -X utf8 var/_dead_wait_audit.py --n 1200 --cands bot.speedc151.SpeedC151,bot.speedc135d.SpeedC135D
```

**2026-09-21 基线读数（当前臂 `speedtugc` vs `speedc151`，供下一役对照）**

| 仪表 | 关键量 | 我们的值 | 顶级值 |
|---|---|---|---|
| ① | **P(live<=14) @1 向听** | **29.7%** | **17.7%** |
| ① | 窄尾的按巡轨迹 | 巡 5: 21.7% → **巡 9: 41.2%** | 15.7% → **9.1%** |
| ② | 第 4→7 次弃牌前进率（1 向听起） | **58.0%** (n=6,215) | **64.5%** (n=6,556) |
| ② | 同口径 2 向听起 | 22.4% | 27.7% |
| ③ | 1 向听对子数 | `speedc151` **1.83** | **1.75** |
| ④ | 死等局面上仍选死等 | **c151/c135d 均 278/330 = 84.2%**（与基线逐位相同） |

**判读纪律**：
- **§10.9 的表是"机制轴"读出，不是判据**；判据仍是 §11.3 的 raw t + adj t≥0 + 第一率护栏；
- 但按 §3.1 的原文 —— **"若这些没动 ⇒ 干预没生效，应停臂而不是等分数"** —— 若下一批臂**连窄尾/前进率都没动**，就不要等分数了。
### §10.10 ★ **100 房/臂** 时的动作表（runbook 补漏，2026-09-21 R848）

> **来源**：本役预登记 `docs/预登记-三臂战役-20260920.md` **§2（L58）**、**§10.2（L108）**、**§11.3（L289）**
> —— 三处一致写着 **"`|t| < 0.60 @100 房` ⇒ futility"**。
> **我原来的 §10.1 清单漏了这条** ⇒ 若不加，可能把一个已 futility 的战役**白跑到 225 房（浪费约 2 天）**。

**到 100 房/臂时，按此表机械判读（raw t 为主，护栏见 §11.3）：**

| 100 房读数（raw t） | 动作 |
|---|---|
| **\|t\| < 0.60** | ★ **futility ⇒ 判 null 并停役，不延长到 225 房**（§11.3 原文："停，不再延期"） |
| **0.60 ≤ t < 1.50** | 继续攒到 **150 房**（主判据点），再用同一阈值重判 |
| **150 房时 0.60 ≤ t < 1.50** | 按 §11.3 **延长到 ~225 房/臂**（最后手段 300）后重判；—— 这是**按 §11.2 功率表设计好的**：225 房时 +29 的效应恰好 t=1.50（⚠ 不是“移动球门”） |
| **t ≥ 1.50 且三护栏全过**（raw t / **adj t ≥ 0** / **第一率 ≥ 基线**） | 可在 150 房直接采用（中期采用还要 **t ≥ 3.00**） |
| **t ≤ −3.0** | 按既有 drop-arm 规则停臂（维持基线） |

**跑法**（100 房时）：
```powershell
python -X utf8 tools/ab_readout.py --since "<本役 started>"      # 看 raw t 与护栏
python -X utf8 var/_first_rate_readout.py --since "2026-09-20 14:54:07"   # 第一率护栏（口径提醒见 §10.14）
# ★★ 第一率护栏以 **ab_readout 的逐臂那一行**（46/46 房）为准：
#    _first_rate_readout 走"按策略名"归属，会把 A/B 之前就已开打的 4 房旧批次算进基线
#    ⇒ 基线被拉低、候选优势被系统性高估（R871 ⑥）。两者不一致时**先查归属，不要先高兴**。
python -X utf8 tools/ab_adopt.py speedc151 --dry-run                # 三护栏 + 判词（dry-run）
# ★ R884 起：预登记的降低门槛两档**已可执行**（默认不生效，必须显式开关）：
#   §2.2   临时采用：t>=1.28 且 >=100 房/臂（下一役强制复核）
python -X utf8 tools/ab_adopt.py speedc151 --provisional --dry-run
#   §2.2-bis 非劣性（**机制前提必须成立**）：t>-1.28 且 >=100 房/臂
python -X utf8 tools/ab_adopt.py speedc151 --noninf --dry-run
#   → 两档都保留第一率护栏（候选不低于基线）；桌强调整后 t 在这两档里**仅提示、不阻塞**（预登记原文如此）。
#   当前（2026-09-21 16:4x）本役 t 在下滑：46 房 1.38 → 48 房 1.06 ⇒ 终点很可能只能走 **--noninf**。
python -X utf8 var/_breaker_watch.py                                # 熔断余量
```

⚠ **futility 是"停"，不是"判负后重开"**：§11.3 明写"若 150 房读数落在 Δ<+20 或 t<1.20，**不允许**再用任何理由延期"。
⚠ **不得在役中改阈值/护栏**（§4/§10.2/§11.3 一致）。
### §10.11 ★ 若裁定"按**第一率**判"：执行口径预案（2026-09-21 R852）

> **背景（R849）**：本役预登记 **§2 明写"主判据 = 第一率（用户裁定 R522：score-side 唯一裁决量）、副判据 = 分/房"**，
> 而 **§6.2 / §10.4 / §11.3 的机械判决落在"净分 t"上、第一率只当护栏** ⇒ 两者不是同一个端点。
> **R850 已量化**：按当前点估计，**两种口径在 100/150 房都会过 1.50** ⇒ 不急于裁定。
> **本节只是把"按第一率判"这条路的机械执行预先写好**，让任何一种裁定都能照抄执行（**不预设裁定结果**）。

**A. 若裁定"按第一率判"（§2 口径）**

| 项 | 口径 |
|---|---|
| **主统计量** | **第一率的 z**（`var/_first_rate_readout.py`，两比例 z） |
| **护栏** | **分/房不为负**（净分点估计 ≥ 0，且**桌强调整后不为负**）—— 即把 R663 的护栏**镜像**过来 |
| **中期采用** | `\|z\| ≥ 3.00` 且各 ≥12 房（对应 §10.2 的中期规则） |
| **终点采用** | `\|z\| ≥ 1.50`（组合臂；单变量用 1.96）且各 ≥150 房 |
| **futility @100 房** | `\|z\| < 0.60` ⇒ 判 null 并停（对应 §10.10） |
| **延期规则** | `0.60 ≤ z < 1.50` ⇒ 延长到 225 房，同阈值重判 |
| **跑法** | `python -X utf8 var/_first_rate_readout.py --since "<started>"`（输出未调整与**桌强调整后**两个差值 + z） |

**B. 若裁定"按净分 t 判"（§6/§10/§11 现状）**

- 即现成流程：`tools/ab_adopt.py speedc151 --dry-run`（raw t ≥ 阈值 / **adj t ≥ 0** / **第一率 ≥ 基线**）+ §10.10 的 100 房动作表。

**C. 150 房的投影（R850 算过，供到点一眼比对）**

| 端点 | 150 房投影 | 过 1.50 所需真实效应 |
|---|---|---|
| 净分 t | **2.28** | ≥ 31.8（当前估计的 **66%**） |
| 第一率 z | **1.89** | ≥ 5.9pp（当前估计的 **79%**） |

⇒ **分叉窗口 = 真实效应缩水到当前估计的 66%~79%**；到点若落在此区间，才需要真正裁定。
⚠ **不论选哪条，都不得在中途改阈值/护栏**（§4/§10.2/§11.3）。
### §10.12 ★ 门禁的**总时长预算**（2026-09-21 R859，按本会话实测）

> 到点那一轮要跑的东西**不是几分钟**：**合计 ≈ 35~40 分钟**，且其中两块就走掉 26 分钟
> ⇒ **必须提前起跑、并确保机器全程空闲**（§10.6）。

| 步骤 | 实测耗时 | 备注 |
|---|---|---|
| **① `fetch_room_replays.py --since … --rooms 120 --gap 0.4`** | **~9 min**（516s，R834） | **必须最先跑**；不跑则所有基于复盘的读出都是陈旧数据（§10.7/R858） |
| **② `_wait_quality.py`** | **~17 min**（R811） | 全语料重算向听，最重的一块 |
| ③ `_ukeire_width.py --rooms 120 --per-role 600` | ~40~50 s | 含按巡分层 + 窄尾 + 按臂窄尾 |
| ④ `_advance_from_common_origin.py --rooms 300 --k0 4 --k1 7` | **~2 min**（110s） | 共同起点前进率 |
| ⑤ `_tenpai_by_arm.py --since …` | ~3 min | 按臂三轴 |
| ⑥ `_improve_rate.py --rooms 120` | ~30 s | 向听前进率 |
| ⑦ `_shanten1_shape.py --rooms 400` | ~10 s | 1 向听形态 |
| ⑧ `_dead_wait_audit.py --n 1200 --cands …` | ~10 s | 死等审计（n=12000 时 ~40 s） |
| ⑨ `ab_readout` / `_first_rate_readout` / `_power_two_endpoints` / `_breaker_watch` / `ab_adopt --dry-run` | 秒级 | 判据与护栏 |
| **合计** | **≈ 35~40 min** | 其中 **①+② = 26 min** |

**⇒ 到点建议**：**目标时刻前 40 分钟**开始（例如 ETA 09-22 18:29 ⇒ **17:45 起跑**），
并按 §10.7 的顺序：**先补抓 → 再跑覆盖率/机制类读出 → 最后跑判据类**。
⚠ 若在 **T-6h 维护窗口**里跑（§3-ter），要预留这 40 分钟 + M=10 门禁的时间。
  ⚠ **R872 实测收紧（2026-09-21 15:57）**：本役 96 个开房周期均值 **15.53 min ⇒ 3.86 房/h**；20min 看门狗误触发率仅 **2.1%**（非 5~8%）⇒ ETA 按实测收紧到 **18:29**，**改 17:45 起跑**。

> **退出码补充（R969）**：若 `run_bot` 在日志已写 `本场结束 finished` 后因 `404 TOURNAMENT_GONE` 退出 2，
> 这是**平台房间清理**，不是策略故障；看门狗应同臂重跑，数据完整性不受影响。

### §10.13 ★ 巡检纪律：进程必须同时匹配 `python` 与 `pythonw`（2026-09-21 R870）

> **教训（我本人在 15:51 犯过）**：自愈任务 `HangzhouMajAutoHeal` 是以
> **`pythonw.exe`** 启动 `_ensure_all.py` 的 ⇒ **由计划任务重启过的栈跑在 `pythonw` 名下**。
> 此时若只查 `Get-Process python`，会得到**"0 个进程"的完全错误结论**（我据此一度判定"bot 栈全停"）。

**正确的巡检写法：**

```powershell
Get-Process python,pythonw -ErrorAction SilentlyContinue |
  ForEach-Object { $cl=(Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
                   "{0,6} {1} {2}" -f $_.Id, $_.StartTime.ToString('MM-dd HH:mm:ss'), $cl.Substring([Math]::Max(0,$cl.Length-46)) }
```

**A/B 役期间的期望进程（4 个）**：
`_watchdog.py` / `_ab_driver.py` / `run_bot`（带 `--record-replays`）/ `match_super.py --strategy …`
（**keeper 不在** —— A/B 期间由 `_ab_driver` 取代；`_prod_monitor` **不在自愈清单里**，
其缺失**不影响房间生产**，且它做重离线计算 ⇒ **不在战役期间主动拉起**）

**另**：`_watchdog` 的**卡死阈值是 20 分钟**（本作典型房时长 15.4 min）⇒
若某房超 ~19~20 分钟未完成，**自愈会重启整栈**，驱动随后判"异常结束（无归档记录）⇒ **同臂重跑**"
⇒ 代价 ~1 房（~17 min），**数据不会被污染**（R870 实测：混臂 0 / 非 finished 0）。


> **⚠ R955 补充（2026-09-21 19:1x）**：`run_bot` / `match_super` 在**换房间隙会短暂消失**（约 10~25 秒），
> 因此**不要**用"应有 4 个进程"作硬断言（会误报掉线）。正确巡检顺序：
> ① `_ab_driver` / `_watchdog` **必须常在**（跨房存活）；
> ② **driver 尾部**最后一条 `已排批` 距今应 < 房时长中位数（~15 分钟）+ 余量；
> ③ **最新 `auto_*.log` 应在增长**，或刚以 `bot 退出` 结束；
> ④ `run_bot` / `match_super` 的短暂缺席**不是异常**。

### §10.13-bis 【2026-09-22 R971】**整机重启后的 A/B 恢复**
- 现象：`_watchdog` / `_ab_driver` / `run_bot` / `match_super` **四项同时缺失**，房日志停住。
- 先查：`Get-CimInstance Win32_OperatingSystem | Select LastBootUpTime` 与 Kernel-Power 事件 1074/109。
- 若确认是系统重启：执行 **幂等** `python -X utf8 var\_ensure_all.py`（只启动缺失进程、不杀任何进程）；
  驱动会把重启前未归档的房按“同臂重跑”处理，混臂/非完成应保持 0。
- 恢复验收：driver/watchdog 存在、最新房日志持续增长、`_camp_integrity` 混臂 0 / 非完成 0。

### §10.14 ★ 测量口径纪律（2026-09-21 R871 新增，两条都是"会翻转判词"级别）

**① `--since` 必须是空格形式**（本次缺陷已修，但纪律保留）
- `auto_ranking.jsonl` 的 `ts` 是 `YYYY-MM-DD HH:MM:SS`（**空格**）。写成 ISO 的 `T` 时，
  裸字符串比较里 `" " < "T"` ⇒ **该日全部行被判成"早于 since"**，跨过午夜后等于**整段战役第一天消失**；
- 实测对照（同一份台账、同一时刻）：

  | 写法 | 房数 | 净分 b−a | t | 第一率 b−a |
  |---|---|---|---|---|
  | `2026-09-20T14:54:07`（错） | 30 / 29 | +69.5/房 | **1.52** | +10.0pp |
  | `"2026-09-20 14:54:07"`（对） | **46 / 46** | +52.4/房 | **1.38** | +6.5pp |

  ⇒ 终点阈值正是 **1.50**：**一次 ISO 写法就足以把"未达标"读成"达标"**；
- 已修：`tools/ab_readout.py`（`_norm_since` / `_ts_ge`）、`tools/ab_integrity.py` 都把 `T` 归一化；
  回归：两种写法现在**都给 46/46、t=1.38**；
- ⚠ **在跑的驱动从不受影响**（护栏/熔断取 `var/.ab_mode` 的 `started`，本来就是空格形式）
  ⇒ 本役的预登记阈值、熔断规则、**判据全程未被改动**。

**② "第一率"有两份口径，判据只认排批归属那份**
- `ab_readout.py` → 走 `_ab_log.jsonl` 排批时刻**精确归属** ⇒ 本役 **46 / 46**；
- `_first_rate_readout.py` / `ab_portal_readout.py` → 走 `rooms_for()`（**按策略名**） ⇒ 基线 **50 房**
  （多出的 4 房是 A/B 开始前就已开打的旧批次，策略名同为 `speedtugc`）；
- ⇒ **判据用前者**；后者的用途是"与门户/对手强度校正交叉验证"（R818）。
  两者不一致时**先查归属，不要先高兴**。

**③ 通用纪律**：任何仪器给出的"漂亮数字"，都要与 `var/auto_ranking.jsonl` 的行数（`finished`、按臂）
**交叉核对一次**；房数对不上就**先怀疑边界/口径，再怀疑数据**。

### §10.16 ★ 严禁"solo 小时"：没有对照臂的房 = 烧掉的役位（R876，2026-09-21）

- **定义**：若某个小时内台账里**只有 1 个臂**，该小时就是 solo（无对照）。
  跨时段比分数被 **±180/房的日间漂移**淹没 ⇒ **solo 房对分数判词一文不值**（但对机制统计仍有用）。
- **实测代价**：全史 **828 房里 385 房（46.5%）是 solo**；
  其中 **09-19 08:00 → 09-20 10:00 近 26 小时（约 101 房）只有 `speedc211`，排批日志里无任何 A/B 排批**
  ⇒ 同样的时间本可以跑一轮 `c211 vs tugc` 并拿到判词。
- **纪律**：
  1. A/B 役期间**不得出现 solo 小时**；
  2. 若驱动/看门狗让某臂**单独跑 >2 小时**，必须记录为**役位损失**（而不是"顺便的产量"）；
  3. 定期用下面这条命令自查（按小时分组，看只有一个臂的小时）：
     ```powershell
     python -X utf8 -c "import io,json,collections;h=collections.defaultdict(collections.Counter);[h[ (d:=json.loads(l))['ts'][:13] ].update([d['strategy']]) for l in io.open('var/auto_ranking.jsonl',encoding='utf-8') if l.strip() and json.loads(l).get('status')=='finished'];print('solo hours:',[k for k,v in h.items() if len(v)==1])"
     ```

### §10.17 ★ 下一役启动套件（2026-09-21 R891：**新臂已验证，只差注册 + T-6h 门禁**）

**① 注册（只在本役结束后做；战役期间禁改 `run_bot.py`）**
在 `run_bot.py` 的 `STRATEGY_FACTORIES` 里、**`"speedc151"` 那一行之后**插入四行（纯新增）：

```python
    "speedc230": lambda: __import__("bot.speedc230", fromlist=["SpeedC230"]).SpeedC230(),
    "speedroute0": lambda: __import__("bot.speedroute", fromlist=["SpeedRoute0"]).SpeedRoute0(),
    "speedroute2": lambda: __import__("bot.speedroute", fromlist=["SpeedRoute2"]).SpeedRoute2(),
    "speedroute16": lambda: __import__("bot.speedroute", fromlist=["SpeedRoute16"]).SpeedRoute16(),
    "speedroutelate": lambda: __import__("bot.speedroute", fromlist=["SpeedRouteLate"]).SpeedRouteLate(),
    "speedgiveupm2": lambda: __import__("bot.speedgiveup", fromlist=["SpeedGiveupM2"]).SpeedGiveupM2(),
    "speedtenpailive": lambda: __import__("bot.speedtenpai", fromlist=["SpeedTenpaiLive"]).SpeedTenpaiLive(),
    "speedtenpailivefan": lambda: __import__("bot.speedtenpai", fromlist=["SpeedTenpaiLiveFan"]).SpeedTenpaiLiveFan(),   # 占优档（不降番），优先这个
    "speedmeldmore0": lambda: __import__("bot.speedmeldmore", fromlist=["SpeedMeldMore0"]).SpeedMeldMore0(),
    "speedmeldmore2": lambda: __import__("bot.speedmeldmore", fromlist=["SpeedMeldMore2"]).SpeedMeldMore2(),   # R928 推荐: 副露轴候选 (干净分母足迹: 碰 +1.6pp / 吃 +11.8pp)
    "speedgangfixlate": lambda: __import__("bot.speedgangfix", fromlist=["SpeedGangFixLate"]).SpeedGangFixLate(),   # R952 组合臂: P0 杠感知 + 多对子惩罚晚期门控
    "speedstack": lambda: __import__("bot.speedstack", fromlist=["SpeedStack"]).SpeedStack(),   # R962 安全叠加: P0 + routeLate + 最宽吃搭 + 听牌保番活等
    "speedlookahead": lambda: __import__("bot.speedlookahead", fromlist=["SpeedLookahead"]).SpeedLookahead(),   # R963 一步宽度前瞻（叠在 SpeedStack 上）
    "speedlookahead2": lambda: __import__("bot.speedlookahead", fromlist=["SpeedLookahead2"]).SpeedLookahead2(),   # R964 2向听一步宽度前瞻（K=8, margin=0.5）
    "speedlookaheadboth": lambda: __import__("bot.speedlookahead", fromlist=["SpeedLookaheadBoth"]).SpeedLookaheadBoth(),   # R965 s=1+s=2 前瞻组合
    "speedlookaheadtugc": lambda: __import__("bot.speedlookahead_tugc", fromlist=["SpeedLookaheadTUGC"]).SpeedLookaheadTUGC(),   # R970 纯 TUGC + s1/s2 前瞻（c151 失败分支）
```

**①-b 导入自检（不启进程）**
```powershell
python -X utf8 -c "import run_bot; f=run_bot.STRATEGY_FACTORIES; [f[n]() for n in ('speedc230','speedroute0','speedroute2','speedroute16','speedroutelate','speedgiveupm2','speedtenpailive','speedtenpailivefan')]; print('OK', len(f))"
```

**② 上臂前三档冒烟（点号路径可在**注册前**先跑；R873）**
```powershell
foreach ($c in @('bot.speedc230.SpeedC230','bot.speedroute.SpeedRouteLate')) {
  foreach ($k in @('draw','window-live','window-claim')) {
    python -X utf8 tools/arm_smoke.py --kind $k --class $c --n 25
  }
}
```
预期：全部 ✅、退出码 0；`window-live` 那档必须出现非 `pass` 动作。

**③ M=10 延迟门禁（**空档期**；用固定语料，必须记 sha/kind/n；R880）**
命令见 §3（已全部带 `--from-file var/smoke_corpus_v1.jsonl`）。
候选：`bot.speedc230.SpeedC230` / `bot.speedroute.SpeedRouteLate`（两档都跑 draw + window-live）。

**④ 开跑（阵型待裁）**
```powershell
# 推荐阵型（R888/R889 定位：副露质量优先）：
python -X utf8 tools/ab_ctl.py start speedc151,speedc230,speedroutelate 1 --bundles=<待裁>
```
⚠ **`--bundles=` 的内容必须在开跑前决定并写死**（它决定终点阈值：
单变量 1.96 / 组合臂 1.50）：
- `c230` / `speedroutelate` 相对 `c151` 都是**单一变量**改动，但 `c151` 本身是**组合臂**；
- 若按"相对基线只改一处"口径 ⇒ **两个候选都是组合臂**（阈值 1.50）；
- 若按"臂本身是否组合"口径 ⇒ 它们都继承 c151 的组合性（仍 1.50）。
⇒ 两种口径结果一致（**1.50**），但仍需在预登记里**写明**。


---

### §10.18 ★ P0 预制补丁：**带杠手牌的副露能力被永久堵死**（R937，2026-09-21）

> **本役期间禁止施加本补丁**（改的是 `decide` 路径 = 热路径）。
> **执行时机**：本役判决落地后、下一役开跑前的窗口，**且必须先过 M=10 延迟门禁**。

#### 证据（真机 + 代码）
- 真机（事件流口径）：**ME 在含杠手里"杠后吃碰" 0/34 = 0.0%**，而 **TOP32 = 23.7%**（均 0.263 次）；
  0/34 vs 23.7% 的二项 p ≈ 1e-4。
- 代码：带杠手牌暗牌 = `14-3e-g ≡ 13-3e`（杠按 3 张计），但三处写死 `13-3e-g`：
  ```python
  bot/speedc136.py:87   if not offer or len(hand) != 13 - 3 * e - g:  return False      # _want_claim
  bot/speedtugc.py:172  if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:       # decide 的 chi 分支
  bot/speedc136.py:63   if len(h3) != 13 - 3 * e2 - g2:  continue                       # _after_best 内层
  ```
- 量级（`var/_gang_fix_check.py`，2358 个含杠弃牌样本）：
  **旧法成功 0 / 抛错 2358 = 100%**；**新法（`gangs=0`）成功 2354 = 99.8%，`real_ukeire` 100% 成功**；
  新法向听分布 0:1372 / 1:659 / 2:258 / 3:60 / 4+:5（合理）。

#### 精确改法（三处，必须同时改；否则仍被其余检查挡住）
```python
# ① bot/speedc136.py  _want_claim 内（约 L85-90）
e = len(melds)
g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
# R937: 带杠手牌暗牌 = 14-3e-g == 13-3e（杠按 3 张计）⇒ 内部一律按 gangs=0 评估
if not offer or len(hand) != 13 - 3 * e:
    return False
vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
before = _state(hand, e, 0, self.GOD_MELD)          # ← 原为 (hand, e, g, ...)
#   （同函数内后续所有 _after_best(...) 调用也把 gangs 参数传 0）

# ② bot/speedtugc.py  decide 的 chi 分支（约 L172）
if chi_cnt < 2 and len(hand) == 13 - 3 * exposed:   # ← 去掉 "- gangs"

# ③ bot/speedc136.py  _after_best 内层（约 L63）—— 若调用方已按 gangs=0 传参，
#    此处保持 `13 - 3 * e2 - g2` 即自动一致（因为 g2 随之为 0），**无需改动**；
#    但须补一条断言/单测锁住该等价性。
```
- **非杠手牌是无副作用的**：`g=0` 时 `13-3e == 13-3e-g`，改动为 no-op ⇒ **风险只落在含杠手牌**。
- 杠的**枚举分支**（`gang_ming`: `e2,g2 = exposed+1, gangs+1`）在新约定下仍自洽：
  `13-3(e+1)-1 = 9-3e` 与 `h3 = (13-3e)-4 = 9-3e` 相等 ✅

#### 必过的护栏（实施时新增单测，纳入 `tests/`）
1. **可评估性**：含杠手牌（暗牌 `13-3e` 张）能算出向听与真进张，**不抛异常**；
2. **不再无条件 pass**：对真实含杠窗口，`_want_claim` 的返回值不再恒为 False；
3. **非杠不变**：在固定语料 `var/smoke_corpus_v1.jsonl`（sha256 `d2c4602c1f69b48d`）上，
   非杠局面的决策与改前**逐位一致**（回归护栏）；
4. **M=10 延迟门禁**：`--from-file var/smoke_corpus_v1.jsonl`，draw + window-live 两档，记 sha/kind/n。
---

### §10.19 ★ 双固定语料（R944，2026-09-21）—— 今后**每个臂**的验收基线

| 语料 | 规模 | sha256 | 用途 | 阈值 |
|---|---|---|---|---|
| `var/smoke_corpus_v1.jsonl` | 5718 | `d2c4602c1f69b48d` | **非杠零回归** | **与对照臂逐位相同** |
| **`var/smoke_corpus_gang_v1.jsonl`** | **4007**（1杠3902/2杠105） | 前16 `dff0265da95241eb` | **带杠类保向听率** | **≥99%** |

**为什么需要第二份**：`v1` 里**带杠局面 = 0**（R942 发现）⇒ 单靠 v1，**所有带杠类缺陷都不会被验收发现**。
实测对照（R944）：`c151` 在带杠语料上保向听率 **34.0%**，`SpeedGangFix` **100.0%**。

> ⚠ **口径警告（R945）**：语料用 `track` 的**重建手牌顺序**，而生产 `my_hand` 的顺序不同
> ⇒ **34.0% 不是生产严重度**：真机（实际出牌）测得的保向听率是 **83.1%**（R939）。
> ⇒ 本语料**只用于臂间相对比较**（修 vs 不修）；引用时必须注明「顺序相关、非生产严重度」。
> ⇒ 可寻回损失按生产口径 = **16.9% 的含杠弃牌**。
> 语料 sha256 前16（修正 `t` 字段后）= **`31b11bafb71163d1`**。

**候选验收清单（新增第 5 条）**
1. 三档冒烟（`draw`/`window-live`/`window-claim`）全 ✅，`window-live` 有非 `pass`；
2. **非杠零回归**：在 `v1` 上与对照臂**逐位一致**；
3. **带杠保向听率**：在 `smoke_corpus_gang_v1.jsonl` 上 **≥99%**；
4. M=10 延迟门禁（`--from-file`，记 sha/kind/n）；
5. 有护栏单测（≥3 条，含反向护栏）。

**重放生成**：`python -X utf8 var/_make_gang_corpus.py`（确定性；生成后应复核 sha256 是否一致）。
**验收器**：`python -X utf8 var/_gang_corpus_verify.py`。
---

### §10.20 ★ 本役结束后的"一条龙"命令块（R954，已逐条验过 CLI）

> **前提**：① 本役已判决并停止（无对局在跑）；② 机器空闲（M=10 必须空档，R807/R859）。
> 逐条复制执行；**M=10 那一步必须记录 `sha/kind/n`**（工具会自己打印 sha）。

```powershell
# 0) 停役后确认无对局进程（应为 0）
(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_bot|match_super' -and $_.Name -match 'python' } | Measure-Object).Count

# 1) 注册（runbook §10.17 的 16 行；只在本役结束后做）
#    插入后自检：路径与类名是否都能实例化
python -X utf8 -c "import importlib; [getattr(importlib.import_module(m), c)() for m, c in [('bot.speedgangfix','SpeedGangFixLate'),('bot.speedroute','SpeedRouteLate'),('bot.speedc230','SpeedC230'),('bot.speedtenpai','SpeedTenpaiLiveFan'),('bot.speedmeldmore','SpeedMeldMore2'),('bot.speedstack','SpeedStack'),('bot.speedlookahead','SpeedLookahead'),('bot.speedlookahead','SpeedLookahead2'),('bot.speedlookahead','SpeedLookaheadBoth'),('bot.speedlookahead_tugc','SpeedLookaheadTUGC')]]; print('导入自检 OK')"

# 2) 三档冒烟（点号路径，注册前后都可跑；window-live 必须有非 pass）
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedgangfix.SpeedGangFixLate --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedgangfix.SpeedGangFixLate --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedgangfix.SpeedGangFixLate --n 30
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedstack.SpeedStack --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedstack.SpeedStack --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedstack.SpeedStack --n 30
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedlookahead.SpeedLookahead --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedlookahead.SpeedLookahead --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedlookahead.SpeedLookahead --n 30
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedlookahead.SpeedLookahead2 --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedlookahead.SpeedLookahead2 --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedlookahead.SpeedLookahead2 --n 30
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedlookahead.SpeedLookaheadBoth --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedlookahead.SpeedLookaheadBoth --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedlookahead.SpeedLookaheadBoth --n 30
python -X utf8 tools/arm_smoke.py --kind draw         --class bot.speedlookahead_tugc.SpeedLookaheadTUGC --n 30
python -X utf8 tools/arm_smoke.py --kind window-live  --class bot.speedlookahead_tugc.SpeedLookaheadTUGC --n 30
python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedlookahead_tugc.SpeedLookaheadTUGC --n 30

# 3) ★ M=10 延迟门禁（空档；每臂三种 kind 各一遍；必须记 sha/kind/n）
python -X utf8 var/_concurrency_bench.py bot.speedgangfix.SpeedGangFixLate --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedgangfix.SpeedGangFixLate --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedgangfix.SpeedGangFixLate --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_concurrency_bench.py bot.speedstack.SpeedStack --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedstack.SpeedStack --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedstack.SpeedStack --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead2 --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead2 --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookahead2 --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookahead2 --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind draw
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookahead2 --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind window-live
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookaheadBoth --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookaheadBoth --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedlookahead.SpeedLookaheadBoth --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookaheadBoth --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind draw
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookaheadBoth --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind window-live
python -X utf8 var/_concurrency_bench.py bot.speedlookahead_tugc.SpeedLookaheadTUGC --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind draw
python -X utf8 var/_concurrency_bench.py bot.speedlookahead_tugc.SpeedLookaheadTUGC --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window
python -X utf8 var/_concurrency_bench.py bot.speedlookahead_tugc.SpeedLookaheadTUGC --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 200 --warm 0 --kind window-live
python -X utf8 var/_m10_divergence.py bot.speedlookahead_tugc.SpeedLookaheadTUGC --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind draw
python -X utf8 var/_m10_divergence.py bot.speedlookahead_tugc.SpeedLookaheadTUGC --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind window-live
python -X utf8 var/_m10_divergence.py bot.speedstack.SpeedStack --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind draw
python -X utf8 var/_m10_divergence.py bot.speedstack.SpeedStack --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind window-live
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookahead --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind draw
python -X utf8 var/_m10_divergence.py bot.speedlookahead.SpeedLookahead --from-file var/smoke_corpus_v1.jsonl --threads 10 --per-thread 50 --kind window-live

# 4) 双语料验收（非杠零回归 + 带杠保向听）
python -X utf8 var/_gangfixlate_accept.py        # 期望：① 100% 逐位一致  ② 100% 保向听
python -X utf8 tests/test_speedgangfix.py        # 期望：8/8 OK
python -X utf8 var/_stack_accept.py               # 期望：非杠只改听牌 1.84%，带杠 4007/4007 保向听
python -X utf8 tests/test_speedstack.py          # 期望：5/5 OK
python -X utf8 var/_lookahead_arm_check.py      # 期望：19.5% 改写、56 好 / 13 差、均值 +0.095 live
python -X utf8 var/_lookahead_arm_check.py 8 10 300 2  # 期望：s2 改写 21/17好4差，净 +49.1 live
python -X utf8 var/_lookahead_arm_check.py 4 10 300 0  # 期望：both 24改/18好2差，净 +25.2 live
python -X utf8 tests/test_speedlookahead.py     # 期望：10/10 OK
python -X utf8 tests/test_speedlookahead_tugc.py  # 期望：3/3 OK

# 5) 起跑（阵型与 --bundles 以用户裁定为准；示例）
python -X utf8 tools/ab_ctl.py start speedc151,speedlookahead2,speedlookaheadboth 1 --bundles=speedlookahead2,speedlookaheadboth  # 判决后按分支替换基线
```

**验收锚（本会话已实测）**：非杠逐位一致 **1500/1500**；带杠保向听 **4007/4007**；护栏 **8/8**；
三档冒烟 **3/3**；端到端 `decide` **0 异常**；**M=10 与真机 A/B 待做**。

⚠ **`window-live` 的 fixture 归属不可判**（R925）⇒ 它只作"不抛异常/分支覆盖"，**不作效果**用。