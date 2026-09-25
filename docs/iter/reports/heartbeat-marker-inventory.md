# 运行期标记总账（谁写 / 谁读 / 看护第几步报）—— R1492/§V.217

> 为什么要有这张表：这一周**同类"写了但没人执行/没人读"**抓出 **12 个**（见 journal R1460–R1491）。
> 与其一个个找，不如**把全部运行期标记列成总账**，并规定：**任何新标记必须同时给出"看护第几步报"或"哪个代码读它"**。
> 纪律：**看护只报，不自己动手**（恢复/丢役/上线一律给命令由人定）。

| 标记（`var/` 下） | 写入者 | 谁**读**它 | 看护步骤 | 人看到之后做什么 |
|---|---|---|---|---|
| `.CAMPAIGN_ABORTED` | `_ab_driver.py`（熔断） | — | **0** | 按文件里的两条命令续役或降为基线（**不自动执行**） |
| `.YAKU_NEXT_PENDING` | `_next_yaku_notice.py` | — | **0b** | §V.186 判断题：定"开不开役 5、开哪个" |
| `.mech_warn` | `_mech_watch.py` | **`_adopt_pair.mech_state()`** | **0c** | 该臂按 B3 不采用；先看数字再定性（家族预期 ≠ 该役 §2 阈值） |
| `.v_mech_unknown` | `_mech_watch.py` | — | **0c** | 等样本（~40 房/臂自动判、**自动清**） |
| `.B2_CANDIDATES` | `_adopt_pair.py` | — | **0d** | 机制成立/主端点未证实 ⇒ 供人并行比较（不进自动池） |
| `.VERDICT_RULE_CONFLICT` | `_adopt_pair.py` | — | **0e** | 按 `yaku3-verdict-readcard.md` §0 定性（V 的 B1 是否成立） |
| `.EVENT_SWITCH_BLOCKED` | `_final_event_switch.py`**与** `_final_event_ready.py` | — | **0f** | 10/10 上线没成功：照抄文件里的命令（含 `-AllowNotReady` 逃生阀、ycbk 孪生） |
| `.SCHEDULE_TIGHT` | `_schedule_guard.py` | — | **0g** | 排期不够 ⇒ 按 §V.160 丢弃顺序**丢一个役**（丢哪个由人定） |
| `.FINAL_ARM_UNRESOLVED` | `_final_arm_confirm.py` | — | **0g** | 定臂被拒（臂未注册/不能实例化）⇒ 10/7 换臂会失败 |
| `.FINAL_NOT_READY` / `.FINAL_READY` | `_final_ready_check.py` | — | **0g** | 就绪校验 FAIL 清单（10/7 10:30 / 10/8 09:00 各跑一次） |
| `.final_submitted` | `_submit_final.py` | `_submit_final.py`（幂等） | **0g** | 10/8 提交已完成（**成功**标记） |
| `.portal_URGENT` | `_portal_watch.py` | — | **0g** | 门户紧急告警（另见 `var/_portal_alert.log`） |
| `.portal_new_event` | `_portal_watch.py` | — | **0g** | 门户出现新赛事（可能是 10/10 的赛事） |
| `.ab_mode` | `tools/ab_ctl.py` / `var/_bsegment.py` | `_ab_driver` / `_verdict_watch` / `_mech_watch` / `_schedule_guard` / `_replay_guard` / `_ensure_all` … | 1 / 2 | 当前役的唯一权威（臂集 + `started` + `bundles`） |
| `.ab_mode.last` | `_ensure_all.py`（每 5 分钟快照） | 人（恢复用） | 2 | `.ab_mode` 消失后的唯一可信恢复来源 |
| `.pause_mode` / `.official_mode` | 人 / 事件链 | `_feature_mode` / `_ensure_all` / `_ab_driver` / `_official_guard` … | 2 | 平台暂停 / 正式赛模式（正常状态，看护静默） |
| `.final_arm.txt` | `_final_arm_confirm.py` | `_switch_final.py` / `_final_event_switch.py` / `_final_ready_check.py` | 0g / 3 | 10/7 换臂的目标臂；**缺 ⇒ 换臂与上线都 fail-closed** |
| `.rate_guard_off` / `.final_installed` | `_switch_final.py` | `_final_ready_check.py` | 3 | 换臂已完成 + 熔断已关（防换臂被熔断回退） |
| `.adopted_*` / `.verdict_done_*` / `.verdict_last_*` | 判词/采用看护链 | `_adopt_when_ready` / `_adopt_pair` / `_final_arm_confirm` | 1 | 幂等与"同一役只报一次"的依据 |
| `.strong_veto_<label>` | `_adopt_when_ready.py --strong-veto` | — | —（**历史**） | 役 2 采用时**未走** `--strong-veto`（当时注册的任务没带该开关）；事后分层读数两层都偏 `speedvalue`，**结论不变**。后续役由 `_adopt_pair` 内部完成否决 |

## 非标记（凭据 / 文件后缀）—— 不是状态标记，但也在 `var/` 下，一并登记

| 名字 | 是什么 | 谁管 |
|---|---|---|
| `.token_final_20261010` | **10/10 正式赛令牌**（唯一人工输入） | `_final_event_switch.py` / `_final_event_ready.py` 读它；**缺 ⇒ 不上线** |
| `.portal_cookie` | 门户认证 cookie（**凭据**） | `_portal_watch.py` / `_final_event_switch.py`；泄密门会拦“纯 cookie 小文件” |
| `.bak` | 备份文件**后缀**（不是状态） | 9/25 已清理误入仓的 4 个（R1479） |

## 说明

- **"谁读它 = —"不等于没用**：这类是**给人/看护看的**状态标记，出口就是上表的"看护步骤"。
- **自动读的**（如 `.mech_warn` → `_adopt_pair`、`.final_arm.txt` → `_switch_final`）已经在代码里 fail-closed。
- **报的节奏**：长期有效的标记（如 `.SCHEDULE_TIGHT` / `.FINAL_NOT_READY`）**只在“首次出现或内容变化”时报一次** ——
  每 2 小时重复报同一件事，会把警报变成噪声（等于又一个静默失效）。
- **新增标记的规矩**：同一次改动里必须同时给出 ① 写完在哪清 ② 谁读（或看护第几步报）。否则就是在制造第 13 个"没人执行"。
