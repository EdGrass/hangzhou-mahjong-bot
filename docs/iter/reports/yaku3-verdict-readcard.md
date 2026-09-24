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
