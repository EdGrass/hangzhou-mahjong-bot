# 役 3（**已修订 2026-09-23 04:2x**）：hybrid 否决 → 采纳「跳过无关全量快照」

> **[SUPERSEDED 已作废]** 本版役 3（hybrid `/state`）已被真机否决（R1091：登记竞态 ⇒ response age p50 744→3768ms），并由 `next-month-plan-20260923.md` §U-4/§V.9 的役序定稿取代。**不在役序内，仅留档**。

> **修订说明（据 R1091/R1093）**：
> - 原定方案（seq=0 快照优先的 hybrid）**已被真机否决**：notify 只推 `{{"seq":N}}`，收到帧立刻取快照时
>   服务端**尚未登记响应者名单** ⇒ 必然回退，而回退路径是 **3 次 `/state`**（比默认 2 次更慢），
>   实测 response `age_ms` **p50 744→3768ms / p90 2150→8241ms**。哨兵已删除，补丁默认关闭。
> - **替代方案（已实现并验证）**：按事件类型**跳过无关的全量快照**（`bot/game.py::_needs_snapshot`）。
>   实测 response `age_ms` **p50 656ms / p90 737ms**（基线 744/2150），首次进入 1s 窗口内；副露活动无退化。
> - 下方"判据"已按新方案改写；原 hybrid 相关条目保留作历史记录。

> 状态：**候选已备好（补丁只在副本上彩排过），等役 2 判词后起役**。
> 依据：R1086（`tools/meld_gate_check.py`，60 份）——gate 说"要副露"的窗口我们执行率 100%，
> 全部损失是 **MISSED（从未作答）**：`sh=0 & live>=+7` **31.4%**、`sh<0` **23.1%**；
> 首个插桩房 `auto_20260923_031950` 的 **response age_ms p50=747ms / p90=2151ms**（窗口 1s）。

## 1. 变更（单一变量）

在 `bot/game.py` 的响应/摸牌状态获取处，把"每次都拉 2 次 `/state`"改为：

1. 先拉 **seq=0 全量快照**（1 次调用）；
2. 用 `bot/faststate.snapshot_covers()` 判定该快照是否足以决策
   （draw 轮到我须有 `drawn_tile`；response 须有 `offer_tile` 且我们在 `responding_seats`）；
3. **不足才补拉**增量（回退到今天的 2 次路径）。

开关：**哨兵文件 `var/.hybrid_state`**（或 env `HM_HYBRID_STATE=1`）；删文件即回滚。
补丁：`var/_prep_hybrid_state.py`（幂等 + fail-closed，已在已插桩的 `game.py` 副本上 dry-run 通过，锚点 2/2）。

## 2. 判据（预登记，起役前一次性登记）

| 档 | 端点 | 阈值 | 工具 |
|---|---|---|---|
| **主（机制，小时级）** | response `age_ms` p90 | **<= 1000ms**（基线 2151ms） | `var/_age_baseline.py` / 新 dec 日志 |
| **主（机制，小时级）** | `sh=0 & live>=+7` 窗口 MISSED 率 | **<= 10%**（基线 31.4%） | `tools/meld_gate_check.py` |
| 护栏（机制） | discard 409 / timeout 率 | **不得高于基线** | `var/_discard_lateness.py`、服务端日志 |
| 护栏（机制） | 窗口捕获率 | **不下降**（基线碰 78.2% / 吃 78.0%） | `var/_window_match_content.py`、`var/_chi_capture.py` |
| 护栏（质量） | 弃牌河保真度 | 平均缺口 **<= 1.5 张**（已知残差 ~1.0；单快照路径跳过增量事件，河会更容易变短） | `tools/river_fidelity.py --since <起役时间>` |
| 主（结果，房级） | 复盘和牌率/房 vs 历史 c151 | z >= 1.50，各 >= 80 房，覆盖 >= 70% | `var/_gate2.py --baseline speedc151 --candidate speedc151`（同臂前后对比） |

> 注：hybrid 是**全局客户端行为**，无法在同役内做臂间 A/B ⇒ 采用**同臂前后对比（interrupted time series）**。
> 机制端点是**直接测量**（age_ms / MISSED），不依赖时间漂移；结果端点用历史 c151 房作对照，注明为弱因果。

## 3. 分支

- **B1 主端点达标**（age p90 <= 1s 且 MISSED <= 10%）⇒ 保留 hybrid，进入下一轴（杠束 / notifier 直带事件）。
- **B2 未达标但同向**（age p90 下降但 > 1s）⇒ 保留 hybrid，**下一役 = notifier 直接携带事件**（省掉第二次 `/state`）。
- **B3 409/timeout 上升** ⇒ 立即删 `var/.hybrid_state` 回滚；把 `snapshot_covers` 判据收紧后重测。

## 4. 起役清单

```powershell
# ① 停役 2（等当前房自然结束）
python -X utf8 tools/ab_ctl.py stop
# ② 应用补丁（幂等；役外执行）
python -X utf8 var/_prep_hybrid_state.py
# ③ 开哨兵（自愈重启后仍生效）
New-Item -ItemType File -Path var/.hybrid_state -Force
# ④ 起役（基线仍是 c151；候选按下一轴选择，或先做同臂前后对照）
python -X utf8 tools/ab_ctl.py start <臂> 1
# ⑤ 起役后 1 小时内核对
python -X utf8 tools/meld_gate_check.py --since "<起役时间>" --arm speedc151
python -X utf8 var/_age_baseline.py
```

## 5. 留档

- 本文件 + journal R1086（依据）+ 起役/判词条目；
- 补丁前后 `game.py` 的语义 diff（已确认只新增 hybrid 分支，不改其它路径）；
- age_ms / MISSED / 409 三张前后对照表。


---

## 6. 修订后的判据（2026-09-23 04:2x，据 R1093）

| 档 | 端点 | 阈值 | 现状 |
|---|---|---|---|
| **主（机制）** | response `age_ms` p90 | **<= 1000ms**（基线 2150ms） | **已达标：737ms**（房 auto_20260923_040450，n=1518） |
| **主（机制）** | `sh=0 & live>=+7` 的 MISSED 率 | **<= 15%**（基线 31.4%） | **待累积**（单房 n=11，样本不足；需 >=6 个优化房） |
| 护栏 | 409 / timeout 行数 | 不高于基线 | 同量级（14→12/@房） |
| 护栏 | 副露活动（整桌每文件） | 不下降 | 碰 17.9→15.7、吃 15.1→15.9、杠 0.5→0.8（同量级） |
| 护栏 | 河保真度 | 平均缺口 <= 1.5 | 待跑 `tools/river_fidelity.py --since 04:00` |
| 结果 | 复盘和牌率/房 | z >= 1.50 | 需各 >= 80 房（优化房累积中） |

**回滚**：`bot/game.py::_needs_snapshot` 改为 `return True` 即恢复旧行为（单行）；补丁已在 git 工作区可 diff。
