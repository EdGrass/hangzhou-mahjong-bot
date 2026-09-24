# 役 3 预登记（2026-09-23 08:0x 修订）：杠束 `speedgangtakefixed`

> **[SUPERSEDED 已作废]** 本版役 3（杠束）已被役序定稿取代：`next-month-plan-20260923.md` §V.9（庄轴/杠轴撤回与役序定稿）、§V.16（役 4–7 作废重排）。**不在役序内，仅留档**；役 3 现行预登记见 `prereg-campaign3-speedvaluebc-20260924.md`。

> 修订说明：原役 3 = "杠束 + hybrid `/state`"。**hybrid 已被真机否决**（R1091：登记竞态 ⇒ 回退 3 次调用 ⇒ age p50 744→3768ms），
> 且 `/state` 需求削减已以**更稳妥的方式**落地（R1092/R1098：`calls_per_event` 0.60-0.70，对两臂同时生效）。
> 因此本役**只测杠束这一个变量**。

## 1. 臂

| 角色 | 臂 | 说明 |
|---|---|---|
| 基线 | `speedc151` | 当前 keeper |
| 候选 | **`speedgangtakefixed`**（`bot.speedgangtakefixed.SpeedGangTakeFixed`） | 杠束修复版：改善"能杠未杠/杠后处理" |

**入场验证（已完成）**：import OK；`tools/arm_smoke.py` 三档（draw/window-live/window-claim）各 30 局面 **全部通过**，
p50 0-4.6ms、max 169ms；尚未注册进 `run_bot.py`（起役前用换役流程注册）。

## 2. 判据（预登记）

| 档 | 端点 | 阈值 | 工具 |
|---|---|---|---|
| **主** | 复盘**和牌率/房** | z >= 1.50，各臂 **>= 80 房**，覆盖 >= 70% | `var/_gate2.py` |
| 副 | 复盘**番/房** | z >= 1.50 且与主同号 | 同上 |
| 护栏 | ledger 第一率 | 候选 >= 基线 | `tools/_first_rate_readout.py` |
| 护栏 | ledger 净分/房 | 同号（不作阻塞） | `tools/ab_readout.py` |
| 护栏 | 熔断 | 两档不触发 | `var/_breaker_watch.py` |
| 护栏 | 河保真 | 平均缺口（扣吃碰口径）<= 1.5 | `tools/river_fidelity.py --since <起役时间>` |
| 护栏 | 响应健康 | 409 不高于基线（今日基线：全 `response_peng`、7-22 条/房）；429 <= 2 | 房日志 |
| **机制** | 杠/房、副露/房 | **杠/房上升**且和牌率不降 | `var/_gate2.py --mechanism gangs` |

## 3. 事前预测

- 真机缺口：我方与顶级的**杠**差异（历史诊断 +0.88/房方向）；
- 台子证据较弱（p10 t=-2.48，杠系三版之间打平）⇒ **本役以真机为准，台子不作依据**；
- 若主端点达标 ⇒ 采用，keeper 切 `speedgangtakefixed`；若平 ⇒ 按 §B2 不追加同轴改动，转向役 4（副露束）或文档化收尾；
- 若负（z <= -1.50）⇒ 回退 c151，并把杠束归档。

## 4. 起役清单（换役流程，已在役 2 起役时验证过）

```powershell
python -X utf8 tools/ab_ctl.py stop
python -X utf8 var/_prep_next_campaign.py --arm speedgangtakefixed --module bot.speedgangtakefixed --class SpeedGangTakeFixed   # 若被保活守卫拒绝，用等价的手工注册+冒烟路径（见 journal R1082）
python -X utf8 tools/ab_ctl.py start speedc151,speedgangtakefixed 1 --bundles=speedc151
```

## 5. 留档

本文件 + journal 起役/判词条目 + `_gate2.py` 输出 + 采用记录；若采用，更新 `var/_keeper_strategy.txt` 与 `docs/iter/journal.md`。


---

## 6. 修订（2026-09-23 14:3x）：候选必须"挂在上役采用的基线之上"

**发现的问题**：`bot/speedgangtakefixed.py` 的继承链是 `SpeedGangTake -> **SpeedValue**`，
即它 = **speedvalue（出牌轴）+ 杠改动** 的**组合臂**。若以 `speedc151` 为基线去测它，等于把**两个轴捆在一起**，
违反"单变量"预登记纪律（原 §1 的写法有误）。

**正确的候选选择规则**（按役 2 判词分支）：

| 役 2 结果 | 基线 | 候选（= 基线 + 杠改动） | 备注 |
|---|---|---|---|
| **采用** speedvalue | `speedvalue` | `speedgangtakefixed`（已存在，冒烟通过） | 继承链 SpeedValue + gang |
| **不采用** | `speedc151` | **`speedgangtakec151fixed`（本次新建）** | 继承链 SpeedC151 + gang；含杠后弃牌 P0 修复 |

- 新臂：`bot/speedgangtakec151fixed.py`（`SpeedGangTakeC151Fixed`）——
  `SpeedGangTakeC151`（c151 + SELF_GANG + 接受明杠）**加**`_pick_discard_route_gangaware`（杠后弃牌 P0 修复）。
  **入场验证**：import OK（name=speedgangtakec151fixed）；`arm_smoke` 三档（draw/window-live/window-claim）各 30 局面**全部通过**（p50 0-5.9ms、max 53.9ms）。
- **为什么必须带 P0 修复**：R1016 实测杠手状态 0.38% 弃牌命中 `cands empty -> return hand[0]`；只加"更爱杠"而不修它，
  多出的杠会被该 bug 抵消（两者纠缠）。

**本役机制端点（据 R1140 补充）**：除 `杠/房` 外，**必报 `杠开/胡` 与 `杠后胡/杠`**
（真机头对头：我方杠/轮 0.010 vs top32 0.028；杠开/胡 0.50% vs 1.71%；杠后胡/杠 12.8% vs 16.1%）。
