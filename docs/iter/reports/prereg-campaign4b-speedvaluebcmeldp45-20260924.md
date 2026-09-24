# 役 4B 预登记（2026-09-24）：**BC 分支的组合臂** = `SpeedValueBC` + 学习副露（对齐剂量 `claim_p=0.45`）

> 判据**起役前一次性登记**，役中不改。
>
> **⚠ 编号与执行顺序**：本文件是"**役 4 的 BC 分支**"（对应文件名里的 4B）。实际走哪一支由**役 3 判词**决定：
> 若役 3 采用 `speedvaluebc` ⇒ 本节即役 4；若未采用 ⇒ 役 4 用 `prereg-campaign4-speedvaluemeld-20260924.md`（单轴副露）。
> 见 `next-month-plan-20260923.md` §V.49 / §V.57。

## 0. 目标缺口（为什么打这一轴）

- **re-basing 规则**：一旦役 3 采用 `speedvaluebc`，新基线就是它 ⇒ 役 4 必须在**新基线之上**做单变量改动；
- 该分支里两条**可叠加**的轴：**副露（本役）** 与 **爆头可达性 V**（`speedvaluebcv`，另见 §V.45）；
- 副露缺口（同房口径，§V.36）：**TOP32 副露/轮 0.396 vs 我们 0.298（−25%）**；
  而 §V.40 的分解显示"构成"占听牌率缺口的 **30%**（即使全补平也只值 ~−1.5pp 听牌率）⇒ **上限已知**；
- 剂量依据（§V.35）：默认 `claim_p=0.60` 只补 **+10.5%** 副露量，而缺口 ~+20% ⇒ 用**对齐剂量 0.45（+21.0%）**。

## 1. 臂（组合臂；相对新基线的"单变量"）

| 项 | 内容 |
|---|---|
| 类 | `bot/speedvaluebcmeld.SpeedValueBCMeld(claim_p=0.45)`（工厂名 **`speedvaluebcmeldp45`**，本轮 R1278 注册） |
| MRO | `SpeedValueBCMeld → SpeedValueBC → SpeedValueMeld → SpeedValue → SpeedC151 …` ⇒ `_pick_discard` 取 **BC 版**、`_want_claim` 取**副露网版** |
| 相对**新基线 `speedvaluebc`** 的差异 | **只多 `_want_claim` 一层**（draw 层逐位等于 `speedvaluebc` —— 已用单测断言） |
| 剂量 | `claim_p = 0.45`（与 §V.35 单轴对齐剂量一致，**不设阶梯**） |
| 足迹（已测） | draw 层 = BC 的 **15.9%**（不变）；window 层索取率 67.6% → **~82%**（+21% 副露量） |
| 单测 | `tests/test_speedvaluebcmeldp45.py` **4/4**（接线+两模型在场 / draw 等价 BC / window 等价 0.45 档 / 模型缺失退化） |
| 延迟 | Phase A 必跑 `var/_m10_latency_gate.py --arms speedvaluebc,speedvaluebcmeldp45 --calls 60`（**两个模型同时在场**） |

## 2. 判据（预登记，役中不改）

| 档 | 端点 | 阈值 | 工具 |
|---|---|---|---|
| **主** | 复盘**和牌率/房** | **z ≥ 1.50**，各臂 ≥80 房有复盘、覆盖 ≥70% | `var/_gate2.py` |
| 副 | 复盘**番/房** | 与主**同号**（副露换速度的固有代价 ⇒ 允许略降，但不得显著为负） | 同上 |
| **机制（两半都要报）** | ① draw 层改动率（应 ≈ BC 的 15.9%）② **副露/房 ↑、索取率 ↑** | ① ∈ [10%,20%] ② 候选 > 基线 | `_arm_path_audit.py --phase draw` / `--phase window` |
| 护栏 1 | ledger **第一率** | 候选 ≥ 基线 | `var/_first_rate_readout.py` |
| 护栏 2 | ledger **净分/房** | 同号（不阻塞） | `tools/ab_readout.py` |
| 熔断 | `var/_breaker_watch.py` | 两档不触发 | — |

## 3. 事前预测（先写下来）

- **机制**：draw 层与 `speedvaluebc` **完全一致**（组合臂只加索取层）；window 层索取率 67.6% → **~82%**、副露/轮 +~20%；
- **主端点**：BC 的效应 **+** 副露的 +0.5~0.9pp 听牌率（§V.35）⇒ 若 BC 单轴实测 +1~2pp，则组合 **+1.4~2.7pp**；
- **副端点**：番/房 可能略降（副露代价），**净分/房应上升**；
- **最可能结果**：**两半机制都干净**；主端点视 BC 单轴结果**平移**（组合不改变符号）。

## 4. 判词分支

- **B1**：主端点 z ≥ 1.50 且两半机制达标 ⇒ **采用**（keeper = `speedvaluebcmeldp45`）；
- **B2**：机制达标（draw=BC、副露↑）但主端点不达 ⇒ 记"**组合未证实**"，**回到单轴最强的那个**（不追加剂量、不换组合）；
- **B3**：机制**不达标**（draw 层 ≠ BC，或索取率没升）⇒ 作废并回查（模型是否加载 / 视图字段 / MRO 是否被改）。

## 5. 起役清单（三段式窗口，§V.51）

```powershell
# ── Phase A（判决落地后、役 3 仍在跑时做完；全部只读/离线）
python -X utf8 var/_prereg_lint.py
python -X utf8 var/_m10_latency_gate.py --arms speedvaluebc,speedvaluebcmeldp45 --calls 60
python -X utf8 var/_arm_path_audit.py --arms speedvaluebcmeldp45 --baseline speedvaluebc --files 25 --limit 600
python -X utf8 var/_campaign_ready.py --arms speedvaluebcmeldp45 --prereg docs/iter/reports/prereg-campaign4b-speedvaluebcmeldp45-20260924.md --since "<役 4 起点>"
# ── Phase B（窗口 ≈25 秒：dry-run → stop → (P0 已落) → preflight → --go）
python -X utf8 var/_switch_campaign.py --baseline speedvaluebc --candidate speedvaluebcmeldp45        # dry-run
python -X utf8 var/_switch_campaign.py --baseline speedvaluebc --candidate speedvaluebcmeldp45 --go
# ── Phase C：注册判决看护 + 确认第一房
python -X utf8 var/_verdict_watch.py --label 役4b --since "<役 4 起点>" --baseline speedvaluebc --candidate speedvaluebcmeldp45 --mechanism melds --check-only
```

## 6. 已知风险

1. **组合臂不可归因**（两条变量）⇒ 判词必须**两半机制都报**（draw=BC 的 15.9%、window=索取率↑）；
2. **两轴互抵**：BC 是"用进张换价值"、副露是"提速" ⇒ 必须同时看**听牌率**（应↑）与**番/胡**（可能↓），
   不能只看一个（§V.36 的两半框架）；
3. **两个模型同时在场的延迟**：Phase A 的 M=10 门禁必须重跑（BC 网 + 副露网）；
4. **剂量固定 0.45**：不设阶梯；若机制达标而主端点不达 ⇒ **不再加剂量**（与 §V.35 的 B2′ 一致）。

---

## 7. 追加护栏（2026-09-24 09:1x 起役前预登记，R1287）：**强手房一致性**

**为什么**：正式赛（决赛）的对手密度 ≈ **强手房**（top32 在场），而 `_gate2` 主端点是**混合口径**。
⇒ 本役除主端点外，**必须**额外报**分层读数**：
`python -X utf8 var/_verdict_by_elite.py --since "<役起点>" --arms <A>,<B>`
（① **强手房 分/房** ② **强手房 第1率**），以及同席机制口径
`python -X utf8 var/_lowprio_run.py -- python -X utf8 var/_seat_h2h.py --since "<役起点>" --by-arm --top 32`
（**听牌率 / 赢分/轮**，与 `hu_gap_split --by-arm` 互补）。

**判定规则（写死）**
1. 主端点 z ≥ 1.50 且 **强手房两列均不劣于基线** ⇒ **采用**；
2. 主端点 z ≥ 1.50 但 **强手房两列任一显著劣于基线** ⇒ 记 **B2（主端点成立但强手房未确认）**：
   **不作为正式赛选臂**（正式赛几乎全是强手房），继续按役序测下一轴；
3. 强手房样本不足（< 15 房/臂）⇒ 只记录，**不据此翻转**主端点结论。

**口径注**：本节是**起役前追加**（非役中改阈值）；主端点与 z 阈值**一概不变**。
（役 2 的判词仍按它自己的原预登记口径，不适用本节。）

**「显著劣于基线」的钉死定义（R1288）**：强手房分/房的 `候选 − 基线` **< −2×SE合并**
（`SE合并 = sqrt(SE_候选² + SE_基线²)`，各自用强手房子样本的 `SD/√n`）⇒ 判为显著劣化；
若任一侧强手房 < 15 房 ⇒ **不判**（只记录）。本节与 §V.66 的噪声口径一致。

---

## 8. 追加读数列（2026-09-24 09:2x 起役前预登记，R1297）：**决赛相似层（≥2 名 top32）**

**为什么**：实测我方 `分/房` 随**同桌 top32 人数**单调下降 ——
0 个：**+61.0**（n=28）→ 1 个：**−19.4**（n=37）→ 2 个：**−55.6**（n=22）→ **3 个：−95.1（n=8）**；
第 1 率同向（28.6% → 21.6% → 18.2% → **0.0%**）。
而 9/23 三测的**赛事累计**是 `rank=7 / total_score=-277 / games_played=160`（≈ **−92~−138 分/房**，按 2~3 房折算）
⇒ 与我们"3 个 top32"层（−95）**同量级**。
⚠ **勘误（R1298）**：那句"决赛 −138.5/房"的**归因是错的** —— 决赛阶段（21:49–21:55）只有重复的"已确认出席本阶段"，
`status=closed` 时**并没有打到房**（最后一条"本场结束"是 21:45:07，属前一阶段）
⇒ 该数字是**赛事累计**，不是"那一场决赛"的难度。
本节的依据是**难度曲线本身**（+61 → −19 → −56 → −95），与决赛数字无关。

**新增读数（必报，不替代主端点）**
```powershell
# 在 §V.70 的强手房（≥1）之外，再报"≥2 名 top32"层：房数 / 分/房 / 第1率
python -X utf8 var/_verdict_by_elite.py --since "<役起点>" --arms <A>,<B>     # 现有工具（分层列）
```
判定：若该层**样本 ≥ 15 房/臂**，且 `候选 − 基线 < −2×SE合并` ⇒ **按 §V.70 的 B2 处理**（不采用进正式赛）；
样本 < 15 房/臂 ⇒ **只记录**（当前 3 强手层只有 ~5% 的房，约 4 房/臂/役 ⇒ 不可判，必须靠 ≥2 层与 强手房 层叠起来看）。

**参考量级**：本役 95 房里，0/1/2/3 名强手的分布是 **28/37/22/8** ⇒ ≥2 强手占 **31.6%** ⇒ 80 房/臂时可预期 ~25 房/臂，**足够进入判定**。

