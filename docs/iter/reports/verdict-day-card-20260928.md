# 9/28 役3 判词 · **当天操作单**（一屏版）

> 完整口径看 `yaku3-verdict-readcard.md`（当天必读）；本卡只把**那一天真要做的事**列成 6 条。

## 1. 你不用做的（自动）

- `HangzhouMajVerdictWatch3bc` / `3v`（每 10 分钟）：各臂 **≥80 房且复盘覆盖 ≥70%** 时自动写 `var/_verdict_役3bc.txt` / `_verdict_役3v.txt` + 哨兵；
- `HangzhouMajAdoptPairWatch`（每 10 分钟）：两个哨兵齐后，跑强手房否决 → 按**四格**自动起役4。

## 2. 你只需跑一条命令（看全部读数）

```powershell
python -X utf8 var/_verdict_digest.py --since "2026-09-25 20:52:39" --baseline speedvalue ``
    --candidates speedvaluebc,speedvaluebaotouv5 --mechanism none
```

（它只读、不判；顺序 = 2×`_gate2` + 2×强手房否决 + `_pick_arm` + 两半 Pareto）。

## 3. 三种落点与各自含义（预登记字面意思）

| 落点 | 含义 | 役4怎么起 |
|---|---|---|
| `ADOPT speedvaluebc` | BC 判正 | 基线=它，候选=`speedvaluebcmeldp45`（A 行） |
| `ADOPT speedvaluebaotouv5` | V 判正（且 BC 非 ADOPT） | 基线=它，候选=`speedvaluebaotouvmeld`（B 行） |
| 两者都非 ADOPT（`BOXED`/否决） | **NONE 行**（最可能） | 基线=`speedvalue`，候选=`speedvaluemeldp45` |

## 4. 红线（当天最容易踩）

- **绝不手改** `var/_verdict_役3*.txt`（手写一行 `ADOPT` 会静默把四格翻成 A/B 行，把**主端点从未通过**的臂送上 10/7）；
- 到盒仍不决定时，验证文件末条**仍是 `UNDECIDED`** ⇒ 机器按 NONE 行走 ⇒ **没有“等人工破平”的窗口**（破平只在已判正的臂之间）；
- 主端点**未证实**的臂（B2）只作旁证，不进最终候选池。

## 5. 当天另一件要你拍的事（§V.281）

若副露未判正（NONE 行）⇒ 那个空出来的**第三役位** 给不给 `speedvaluerank`？
（默认 **B：不给、保余量**；给的话命令与前提见 `§V.281`）。

## 6. 预期（提前对齐，不是结论）

BC：机制成立、主端点未证实 ⇒ **B2**；V：爆头/胡下降 ⇒ **B3** ⇒ **NONE 行** ⇒ 役4 自动起在 `speedvalue` 上。
