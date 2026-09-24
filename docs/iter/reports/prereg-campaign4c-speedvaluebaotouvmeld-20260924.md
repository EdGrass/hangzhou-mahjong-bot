# 役 4C 预登记（2026-09-24）：**V 分支的组合臂** = `SpeedValueBaotouV5` + 学习副露（对齐剂量 `claim_p=0.45`）

> 判据**起役前一次性登记**，役中不改。
>
> **⚠ 编号与执行顺序**：本文件是"**役 4 的 V 分支**"（文件名里的 4C）。
> 只有当**役 3 判词为「BC 不采用、V 采用」**时才用它（新基线 = `speedvaluebaotouv5`）；
> 其余分支分别用 `prereg-campaign4-speedvaluemeld-*.md`（BC✗V✗）与 `prereg-campaign4b-speedvaluebcmeldp45-*.md`（BC✓）。
> 见 `next-month-plan-20260923.md` §V.49 / §V.57。

## 0. 目标缺口（为什么打这一轴）

- **re-basing 规则**：V 一旦被采用，新基线就是 `speedvaluebaotouv5` ⇒ 役 4 必须在**新基线之上**做单变量改动；
- 该分支里**唯一**还能叠加的轴就是**副露**（窗口层；出牌层已被 V 占用）；
- 副露缺口（同房口径 §V.36）：TOP32 副露/轮 **0.396 vs 我们 0.298（−25%）**；§V.40 分解显示"构成"占听牌率缺口 **30%**；
- 剂量依据（§V.35）：默认 0.60 只补 **+10.5%**、缺口 ~+20% ⇒ 用**对齐剂量 0.45（+21.0%）**。

## 1. 臂（组合臂；相对新基线的"单变量"）

| 项 | 内容 |
|---|---|
| 类 | `bot/speedvaluebaotouvmeld.SpeedValueBaotouVMeld(claim_p=0.45)`（工厂名 **`speedvaluebaotouvmeld`**，本轮 R1279 注册） |
| MRO | `... → SpeedValueBaotouV5 → _BaotouVBase → SpeedValueMeld → SpeedValue → SpeedC151 …` ⇒ `value_of` 取 **V 版**、`_want_claim` 取**副露网版** |
| 相对**新基线 `speedvaluebaotouv5`** 的差异 | **只多 `_want_claim` 一层**（draw 层逐位等于 V 基线 —— 已用单测断言） |
| 剂量 | `claim_p = 0.45`（与 §V.35 对齐剂量一致；**不设阶梯**） |
| 单测 | `tests/test_speedvaluebaotouvmeld.py` **4/4**（接线：claim_p=0.45 / W_TILES=5、副露网在场；**draw 层 ≡ V 基线**；**window 层 ≡ 0.45 档副露臂**；副露网缺失退化不报错） |
| 延迟 | Phase A 必跑 `var/_m10_latency_gate.py --arms speedvaluebaotouv5,speedvaluebaotouvmeld --calls 60`（**V 的 torch 网 + 副露网同时在场**） |

## 2. 判据（预登记，役中不改）

| 档 | 端点 | 阈值 | 工具 |
|---|---|---|---|
| **主** | 复盘**和牌率/房** | **z ≥ 1.50**，各臂 ≥80 房有复盘、覆盖 ≥70% | `var/_gate2.py` |
| 副 | 复盘**番/房** | 与主**同号**；本分支**尤其**要求番/房不得显著为负（V 追爆头的代价要看得见） | 同上 |
| **机制（两半都要报）** | ① draw 层改动率（应 ≈ V 的 13.9~14.8%）② 副露/房 ↑、索取率 ↑ | ① ∈ [10%,20%] ② 候选 > 基线 | `_arm_path_audit.py --phase draw` / `--phase window` |
| **护栏（本分支特有）** | **听牌率 / 胡率** | **不得低于基线 1σ**（V 的换速度风险 + 副露的提速收益，必须净不亏） | `tools/hu_gap_split.py --by-arm` |
| 护栏 2 | ledger 第一率 | 候选 ≥ 基线 | `var/_first_rate_readout.py` |
| 护栏 3 | ledger 净分/房 | 同号（不阻塞） | `tools/ab_readout.py` |
| 熔断 | `var/_breaker_watch.py` | 两档不触发 | — |

## 3. 事前预测

- **机制**：draw 层与 `speedvaluebaotouv5` **完全一致**；window 层索取率 67.6% → **~82%**、副露/轮 +~20%；
- **端点**：V 的效应（爆头/胡 ↑、番/胡 ↑，§V.41）+ 副露的 +0.5~0.9pp 听牌率 ⇒ 主端点**视 V 单轴结果平移**；
- **最可能结果**：两半机制都干净；主端点**灰区**（V 的预期效应 +0.4~1.0pp 和牌率，接近 80 房 MDE）。

## 4. 判词分支

- **B1**：主端点 z ≥ 1.50 且两半机制达标 ⇒ **采用**（keeper = `speedvaluebaotouvmeld`）；
- **B2**：机制达标但主端点不达 ⇒ **回到单轴更强的那个**（不追加剂量、不加新层）；
- **B3**：机制不达标 ⇒ 作废回查（副露网是否加载 / MRO 是否被改 / 视图字段）。

## 5. 起役清单（三段式窗口，§V.51）

```powershell
# ── Phase A（判决落地后、役 3 仍在跑时做完；全部只读/离线）
python -X utf8 var/_prereg_lint.py
python -X utf8 var/_m10_latency_gate.py --arms speedvaluebaotouv5,speedvaluebaotouvmeld --calls 60
python -X utf8 var/_arm_path_audit.py --arms speedvaluebaotouvmeld --baseline speedvaluebaotouv5 --files 25 --limit 600
python -X utf8 var/_campaign_ready.py --arms speedvaluebaotouvmeld --prereg docs/iter/reports/prereg-campaign4c-speedvaluebaotouvmeld-20260924.md --since "<役 4 起点>"
# ── Phase B（≈25 秒：dry-run → stop → (P0 已落) → preflight → --go）
python -X utf8 var/_switch_campaign.py --baseline speedvaluebaotouv5 --candidate speedvaluebaotouvmeld        # dry-run
python -X utf8 var/_switch_campaign.py --baseline speedvaluebaotouv5 --candidate speedvaluebaotouvmeld --go
# ── Phase C
python -X utf8 var/_verdict_watch.py --label 役4c --since "<役 4 起点>" --baseline speedvaluebaotouv5 --candidate speedvaluebaotouvmeld --mechanism melds --check-only
```

## 6. 已知风险

1. **组合臂不可归因**（两条变量）⇒ 必须两半机制都报（draw=V 的 ~14%、window=索取率↑）；
2. **V 与副露可能互抵**：V 追爆头（可能慢）、副露提速（可能降番）⇒ 必须同时看 **听牌率/胡率** 与 **番/胡**；
3. **两个"模型/计算"同时在场**：V 的 torch 网 + 副露网 ⇒ Phase A 的 M=10 门禁必跑；
4. **剂量固定 0.45**：不设阶梯；机制达标而主端点不达 ⇒ **不再加剂量**（与 §V.35 的 B2′ 一致）。

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

