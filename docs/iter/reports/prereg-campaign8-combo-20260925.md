# 预登记：役 5「**叠加验证**」（部署臂选择）—— 起役前一次性登记

> 依据：§V.160（役序）/ §V.161（10/7 换臂口径）/ §V.165（只叠已判正层）/ §V.175（阶段自适应）。
> 判据**起役前一次性登记，役中不改**。

## 0. 目的

役 3/役 4 各自只回答“**这一层有没有用**”。本役只回答一件事：
**把通过的层叠起来，是不是真的比“最优单/双层”更好**（即 10/7 部署哪一个）。

## 1. 臂（起役前填死）

| 角色 | 臂 | 说明 |
|---|---|---|
| 基线 B | `<役 3/4 判正的最优单/双层>` | 例：`speedvaluebc` / `speedvaluebaotouv5` / `speedvalue` |
| 候选 C | `<对应的三层组合>` | 例：`speedvaluebcvmeld`（或剂量对齐版 `…p40`） |

**只允许“已判正层”进组合**（§V.165）：任一层未判正 ⇒ 本次不开它。
组合臂属“多条变量” ⇒ 判据走 **bundle 声明（|t|≥1.50）**，并在 `ab_ctl start` 显式传 `--bundles=B`。

## 2. 端点与护栏

| 档 | 端点 | 阈值 | 工具 |
|---|---|---|---|
| **主** | 同席强手分/房 | **非劣于基线** | `var/_pick_arm.py --strong-top 32` |
| 副 | `_gate2` 和牌率/房 + 番/房 | **z≥1.50 且同向** | `var/_gate2.py --mechanism none --min-rooms 80` |
| 护栏1 | 第1率 | 候选 ≥ 基线 | `_gate2` 内置 |
| 护栏2 | 三层机制 | 各层在带内（新加层拉带；基线已含同层只看 action=0） | `var/_mech_watch.py`（每 6h） |
| **否决** | 强手房两列（分/房、第1率）任一显著劣 | ⇒ **不采用** | `var/_seat_h2h.py --by-arm --top 32` |

## 3. 窗口

初判 **≥30 房/臂**；正式判 **80 房/臂**（有复盘、覆盖 ≥70%）；**役盒 120 房/臂**，到盒按 §V.66 破平，**不延长**。

## 4. 决定规则（写死）

1. 组合**不劣**（主端点非劣 + 副同向 + 护栏过）⇒ **10/7 部署组合臂**（“最屌”）；
2. 组合**显著劣** ⇒ 部署最优单/双层；
3. 不可判定 ⇒ 按 §V.66 破平序列（强手房分/房 → 两半 Pareto → 第1率 → 最近判词 → 基线）；
4. **任何情况下不部署“从未在任何役里判正过”的臂**。

## 5. 起役命令（起役前把 <…> 填死）

```powershell
python -X utf8 var/_arm_path_audit.py --arms <C> --baseline <B> --files 25 --limit 600
python -X utf8 var/_bsegment.py --label 役5 --baseline <B> --candidates <C> --watch-mechanism none          # dry-run
python -X utf8 var/_bsegment.py --label 役5 --baseline <B> --candidates <C> --watch-mechanism none --go     # 真执行
```

读数：`var/_gate2.py --since "<役 5 ts>" --baseline <B> --candidate <C> --mechanism none --min-rooms 80`、
`var/_pick_arm.py --since "<役 5 ts>" --min-rooms 30 --strong-top 32`、`var/_seat_h2h.py --since "<役 5 ts>" --by-arm --top 32`。

## 6. 纪律

判据/阈值/役盒 起役前一次性登记，役中不改；不为追 z 延长；强手房否决优先于主端点。
