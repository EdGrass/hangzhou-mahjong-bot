# 役 3 判词读卡（三臂：`speedvalue` 基线 + `speedvaluebc` + `speedvaluebaotouv5`）

> 判词由两个看护自动落盘：`var/_verdict_役3bc.txt`、`var/_verdict_役3v.txt`
> （各 10 分钟一次；各臂 ≥80 房起判；役盒 120 房/臂）。
> 口径：`since = var/.ab_mode.started`；主+副各 **z≥1.50**；覆盖 **≥70%**；
> 机制端点 = **离线足迹**（`_mech_watch` 每 6h 复核：BC 改动率 ∈[10,20]% 且 action=0）。

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
