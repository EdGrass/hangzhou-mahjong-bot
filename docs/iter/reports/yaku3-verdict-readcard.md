# 役 3 判词读卡（三臂：`speedvalue` 基线 + `speedvaluebc` + `speedvaluebaotouv5`）

> 判词由两个看护自动落盘：`var/_verdict_役3bc.txt`、`var/_verdict_役3v.txt`
> （各 10 分钟一次；各臂 ≥80 房起判；役盒 120 房/臂）。
> 口径：`since = var/.ab_mode.started`；覆盖 **≥70%**；**主端点一律 z≥1.50**。
> **副端点按各自预登记判**（见下）；机制端点 = **足迹 + （V）真实机制**（`_mech_watch` 每 6h）。

## 0. ★ 两个候选的判据**不完全相同**（R1487，必须按各自预登记读）

| 候选 | 主端点 | 副端点 | 机制端点 |
|---|---|---|---|
| `speedvaluebc` | 和牌率/房 **z≥1.50** | 番/房 **z≥1.50 且同向**（campaign3 §2） | 足迹：改动率 ∈[10,20]% 且 action=0 |
| `speedvaluebaotouv5` | 和牌率/房 **z≥1.50** | 番/房 **候选 > 基线**（campaign7 §2：**只看方向**，"本轴的全部理由就是赢得大"） | **爆头/胡 与 赢分/胡 都上升**（足迹只是必要条件；★ R1533 订正：原写“爆头/胡 与 **番/胡**”，而 campaign7 §2 与 `_mech_watch.judge_v_mech`（R1520 起）用 **赢分/胡**；番/胡 仅作读数） |

**⚠ 已知口径冲突（不要临场改判，按下面的规矩处理）**：`_verdict_watch` 里跑的 `_gate2` 对**副端点一律用通用 z≥1.50** ⇒
V 若落在「**主 z ≥ 1.50、副方向为正、但 0 < 副 z < 1.50**」这一格，自动判词会说 `UNDECIDED`（到盒则 `BOXED`），
**但 campaign7 §2 的 B1 其实已经满足**。

- **自动侧已按"不猜"处理**：`_adopt_pair` 识别到这一格 ⇒ **原地不动**、落 `var/.VERDICT_RULE_CONFLICT`（心跳会报）。
- **人要做的**：按 campaign7 §2/§4 定性 —— 主 z≥1.50 且副方向为正且**机制上升** ⇒ 视 V 为 **B1（采用）**；
  只有机制没上升才是 B3（作废）。定性后手工起役（照 §3 的命令）。
- **不允许**的是：让机器按通用 z 口径把它当"不采用"悄悄丢掉。

> 机制端点 = **离线足迹**（`_mech_watch` 每 6h 复核：BC 改动率 ∈[10,20]% 且 action=0）。

> **量纲（R1540）**：`_gate2` 打印的副端点列现在叫 **`番/轮×100`**（它**等于预登记“番/房”端点的一个常数倍变换**）⇒ 判据（z≥1.50、方向）**完全不受影响**；真“番/房”≈ 该值×0.08（8 局/房）。

### 0b. ★ R1534：V 的两条**独立**口径问题（一条是文档、一条是代码）

**(a) campaign7 预登记**自己**措辞不一致**（§2 端点表 vs §3/§4）：

| 位置 | 第二项写的是 |
|---|---|
| **§2 端点表**（标题就是“判据（预登记，役中不改）”） | **赢分/胡** —— 权威 |
| §3 事前预测 / §4 B1 / §4 B2 | 写作 **番/胡** |

**处置**：以 §2 为准（`_mech_watch.judge_v_mech` 自 R1520 起即用「爆头/胡 + **赢分/胡**」，番/胡 仅作读数）；
预登记**役中不改**，所以不动 campaign7 原文，只在此说明。
**对本役无影响**：实测 V 的 **爆头/胡 是下降**的 ⇒ §2、§3、§4 的任何一种读法都判它**不达标**（见下面 (b) 的读数）。

**(b) 代码里 V 的采用路径曾是 fail-open（R1534 已修）**：
`_adopt_pair.mech_state()` 只在 `_mech_watch` **判出“不达标”**时写 `.mech_warn`；判不出（读数缺失/样本不足）写的是
`.v_mech_unknown`，而**除了提醒脚本没有人读它** ⇒ 旧路径把“判不出”当成“无告警＝机制正常”
⇒ **V 可以在机制从未验证的情况下被采用**、并据此起役 4 的 B 行。
**修**：`_adopt_pair.v_mech_verdict()` + `apply_v_gate()` —— 四格若**由 V 决定**（raw row = b）则
V 的机制读数必须是明确的 `pass`：`fail` ⇒ V 记 ✗（B3 作废）、`unknown` ⇒ **原地不动（fail-closed，等人）**。
取“**最新一条 ok 非 None**”的记录（不是“最后一条”），因为 09-26 00:37 实测过一次**解析为空的瞬时抖动**。

---

### 0c. ★ 当前实测**投影**（非判词）：2026-09-26 05:50 · 33 房 · 我方席位

> 来源 `var/_seat_h2h.py --by-arm --top 32`（gid 320）。**只为 9/28 判词当天提前对齐预期**，不是判词。

| 臂 | 局 | 胡/轮 | 番/胡 | 赢/轮 | ⇒ **赢分/胡** | **爆头/胡** | 副露/轮 |
|---|---|---|---|---|---|---|---|
| `speedvalue`（基线） | 880 | 24.66% | 1.28 | +4.51 | 18.29 | 20.7% | 0.328 |
| `speedvaluebc` | 880 | 24.43% | **1.38** | +5.00 | **20.47** | **25.6%** | 0.309 |
| `speedvaluebaotouv5` | 800 | **29.00%** | 1.29 | **+5.59** | 19.28 | **18.5%** | 0.329 |

**读法（重要）**：两个候选的“赢法”**不是一回事** ——

- `speedvaluebc` = **赢得更大**：爆头/胡 **+4.9pp**、番/胡 +0.10、赢分/胡 +2.18 ⇒ **机制两项目前都成立**；
- `speedvaluebaotouv5` = **赢得更频繁**：胡率 **+4.3pp**、赢/轮 +1.08，但 **爆头/胡 −2.2pp** ⇒ **机制第一项不成立**（= campaign7 §2 的 B3）。

⇒ **9/28 最可能的四格（预告，不是结论）**：

| 候选 | 主端点（和牌率/房） | 机制 | 预计落点 |
|---|---|---|---|
| `speedvaluebc` | 与基线**持平**（−0.23pp）⇒ 大概率 z<1.50 | **成立** | **B2**（机制成立、主端点未证实）⇒ campaign3 §4 = 役 4 走 **NONE 行** |
| `speedvaluebaotouv5` | 可能过（+4.3pp） | **不成立** | **B3 作废** ⇒ 不采用 |

**⇒ 若此投影成立，役 3 落 NONE 行、役 4 = `speedvalue` + `speedvaluemeldp45`（副露轴），
`speedvaluebc` 只进 `.B2_CANDIDATES`（供 10/5 提案人工并行比较，不进自动池）。**
这正是“本轴的全部理由就是赢得大”的规矩在起作用：**赢得更频繁 ≠ 赢得更大**，所以 V 不采用。
（人工若认为该把 bc 带上四格，按 §V.247 在 **10/5 提案**里并排比较——提案不受该行限制。）

> **一条命令版（R1547）**：`python -X utf8 var/_verdict_digest.py --since "<役起点>" --baseline speedvalue --candidates speedvaluebc,speedvaluebaotouv5 --mechanism none`（只读；把本卡要求的 6 条命令按**固定顺序**跑完并打一屏摘要；它**不作判断**，读法仍然看本卡）

## 1. 每个候选**各自**读判词

| 判词 | 该轴结论 |
|---|---|
| `ADOPT` | 判正（进入下面四格） |
| `REJECT` | 判负 |
| `REFUSE` | 护栏/机制未过 ⇒ **不采用** |
| `UNDECIDED` 未到盒 | 继续攒房（等看护） |
| `UNDECIDED` 已到盒 | 按 `var/_pick_arm.py` 打印的 §V.66/67 破平序列收口 |

## 2. 强手房否决（本役预登记要求）

主端点 z≥1.50 **但**强手房两列（分/房、第1率）任一显著劣 ⇒ 记 **B2**、**该轴不采用**：

```powershell
python -X utf8 var/_pick_arm.py  --since "<起役ts>" --min-rooms 30 --strong-top 32
python -X utf8 var/_seat_h2h.py  --since "<起役ts>" --by-arm --top 32
```

## 2b. 护栏：提交延迟 / 失效动作

`python -X utf8 var/_submit_latency_audit.py --since "<起役ts>"`（`_mech_watch` 已每 6h 自动跑并记入日志）。
看两件：① **≥1s 提交**（预登记口径 = 超窗 0）；② **真损失类 409**（chi/peng/gang/discard）。
参考（役 2 窗口实测）：p99 1971ms、≥1s 36 次(1.7%)、真损失 409 370 次（~3.1/房）——**已记入 §V.180，作为候选轴**。

## 3. 四格 → 役 4 形态（预登记 §V.160）

| BC | V | 役 4 基线 | 役 4 候选 |
|---|---|---|---|
| ✓ | — | `speedvaluebc` | `speedvaluebcmeldp45` |
| ✗ | ✓ | `speedvaluebaotouv5` | `speedvaluebaotouvmeld` |
| ✗ | ✗ | `speedvalue` | `speedvaluemeldp45` |

一键起役（已支持任意役标签，看护走通用注册器）：

```powershell
python -X utf8 var/_bsegment.py --label 役4 --baseline <基线> --candidates <候选> --watch-mechanism melds          # dry-run
python -X utf8 var/_bsegment.py --label 役4 --baseline <基线> --candidates <候选> --watch-mechanism melds --go     # 真执行
```

（B 段仍依次：停驱动 → 等空档 → P0 补丁 → preflight → 切役 → 注册该役看护；
未选定最终臂 / 非 READY 会拒绝。）

## 4. 纪律

不改阈值、不延长役盒、不为追 z 拖时间；**强手房否决优先于主端点**。

## ★ 追加（R1437）：§2 强手房否决的**机械执行**

> 本节为追补，§2 的要求不变，只是把它变成一条命令 + 一个自动闸。

- 手工：
  ```powershell
  python -X utf8 var/_strong_veto.py --since "<起役ts>" --baseline speedvalue --candidate speedvaluebc
  ```
  退出码 **0=OK（可采用）／3=VETO（显著劣 ⇒ 该轴不采用，四格表里当 ✗）／2=UNKNOWN（强手房 <15 房/臂，不阻塞）**。
- 自动链（注册该役 AdoptWatch 时**必须**带 `--strong-veto`）：
  ```powershell
  python -X utf8 var/_adopt_when_ready.py --label 役3 --baseline speedvalue ^
      --candidates speedvaluebc,speedvaluebaotouv5 --strong-veto
  ```
  ⇒ VETO 时**不执行** B 段，并落 `var/.strong_veto_役3`（等人/看护处理四格表）。
- 分层读数（破平第 ② 步**同口径**）：
  ```powershell
  python -X utf8 var/_strong_slice.py --since "<起役ts>"      # 按它打印的两条命令接着跑
  ```
  参考（役 2 窗口实测）：强手房缺口 听牌率 **−5.19pp** vs 混合口径 −3.14pp。

## ★ 追加（R1438）：§7/§8 两层的**机械判据**

> 追补，不改 §2/§7/§8 的任何阈值与口径。

- `var/_strong_veto.py` 现在**同时判两层**（§7 的 ≥1 名 top32、§8 的 ≥2 名 top32），
  阈值 = **z ≤ −2.0**（逐字等于 §7 的「< −2×SE合并」；**不是** −1.96）：
  ```powershell
  python -X utf8 var/_strong_veto.py --since "<起役ts>" --baseline speedvalue --candidate speedvaluebc
  ```
  任一层在 **净分/房** 或 **第1率** 上显著劣 ⇒ **VETO**；层内 < 15 房/臂 ⇒ 该层**只记录不翻转**。
- §8 层的听牌率读数（切语料后交给现成工具）：
  ```powershell
  python -X utf8 var/_strong_slice.py --since "<起役ts>" --min-elite 2
  python -X utf8 tools/hu_gap_split.py --dirs strong2_<slug>/*.json
  ```
- §8 层的 分/房 + 第1率：`var/_verdict_by_elite.py` 现新增 **`强手房>=2`** 行。
- 参考（役 2 窗口实测，两层方向相反）：≥1 层 −30.5 vs −39.1（z=−0.33）；
  **≥2 层 −82.3 vs −56.5（z=+0.75）、第1率 9.1% vs 18.5%** ⇒ 只看 ≥1 层会漏掉方向翻转。

## ★ 追加（R1439）：役 3 → 役 4 已**无人值守**（补 adopt 看护）

> 追补，§3 的四格表**一字不改**，只是把它接上了自动化。

- 新增 `var/_adopt_pair.py` + 计划任务 **`HangzhouMajAdoptPairWatch`**（每 10 分钟）：
  两个候 selected 哨兵齐后，各自判词（ADOPT 才算）→ 各自跑 `_strong_veto.py`（§7/§8 两层，z ≤ −2.0）
  → 按 **§3 的四格表**调 `_bsegment.py --go --label 役4 ...`。
- 安全口径：**VETO ⇒ 该候选按不采用**；**OK/UNKNOWN ⇒ 采用**（§7.3/§8）；**工具异常 ⇒ 无法判定 ⇒ 原地不动**；
  没到决定性判词 ⇒ 不动；已裁决 ⇒ 幂等 no-op。日志 `var/_adopt_pair.log`。
- 所以役 3 判词落地后**不需要人工接手**；若判成"无法判定"，日志会留痕（那才需要人来看）。

## ★ 追加（R1449）：三臂调度已核（役 3 是首个三臂役）

- 配置：`ab_ctl.build_cfg([3 臂])` → **`files: {"arms": [...]}`**（实测）；两臂仍是旧 `a`/`b`。
- 驱动：`var/_ab_driver.py` 的 `arms_of()` 支持 N 臂、`pick_arm()` 取模轮转、且能从上次的臂接着转 ✓。
  ⇒ **到役 3 起役时不需要改任何调度代码**；起役后只需核对 `.ab_mode.arms` == 期望三臂。

## ★ 追加（R1453）：**V 臂的机制端点 ≠ 离线足迹**（免得判词时读错）

役 3 是两个**不同轴**并排（BC 与 V），它们的预登记**机制端点不一样**：

| 臂 | 预登记机制端点 | 工具 |
|---|---|---|
| `speedvaluebc` | **决策改动率 ∈[10,20]% 且 action 差异 = 0**（离线 draw 足迹） | `tools/offline_replay.py --phase draw`（`_mech_watch` 每 6h 自动跑） |
| `speedvaluebaotouv5` | **爆头/胡 与 赢分/胡 两者均上升**（★ R1520：**已由 `_mech_watch.judge_v_mech` 按此口径执行**；番/胡 仅作读数）（同房口径）；护栏：**胡率不得低于基线 1σ**（★ R1517：**已由 `_mech_watch.judge_v_mech` 执行**；读数缺失 ⇒ 不判） | `var/_seat_h2h.py --by-arm --top 32` + `tools/hu_gap_split.py --by-arm` |

⇒ `_mech_watch` 对 V 臂给出的 "tile 改动 13.5%、action 0% ⇒ PASS" 只是**代用护栏**（同一个"含 baotou 就走 draw 相位"的分支），
**不能代替** V 的机制端点；判词时必须按上表右列**手工并读**。

**另附（campaign7 预登记实测）**：`speedvaluebaotouv5/10/20` 三档足迹 **13.5% / 13.5% / 13.6%** ⇒ **5 已饱和**。
所以 §V.154 ② 说的"剂量档第二枪"**不是换剂量**，而是**再攒 n**（给"不可判定"加功率）；
也正因此，三档都不会越出 10–20% 带 ⇒ `_mech_watch` **不会**因 V 而假告警。
