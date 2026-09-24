# speedtugc 晋级流程（2026-09-11 起草）

## 0. 判定标准（事先写死，避免事后挑标准）

以 A/B 数据（`python var/_ab_analyze.py`，数据源 = 服务器 `total_score` + 复盘机制指标，
**禁用番数重算**，见 E019）判定：

| 指标 | 通过条件 |
|---|---|
| 听牌率 | speedtugc ≥ speedtug（sim 强场预测 +7pp） |
| 胡率 | speedtugc ≥ speedtug（sim 强场预测 +6pp） |
| 副露/局 | speedtugc ≈ 0.8–1.0（机制已达成：真机 0.84 vs 1.24） |
| 服务器分数 | speedtugc 不显著落后（n<20 房/臂时只作参考） |

建议样本量：**≥8–12 房/臂**（听牌率 SE≈2.8–3.5pp）。

## 1. 当前证据（2026-09-11 05:45）

- **sim（修正口径）**：强场(3×TUG) 5seed **+0.075**；混合场 **+0.047**；弱场(3×TM) −0.010
  → 增益随对手变强而增大，非自对弈偏袒（E021/E026）
- **sim 变体穷举**：C045 在 15+ 变体中全部胜出；两个组成部分（严格未听门控 / 已听换听升级）
  均单独验证（C054/C058）
- **真机 A/B（6 vs 4 房）**：speedtugc +130.2/房、名次 1.83、听牌 56.6%、胡 27.2%、副露 0.84；
  speedtug −112.5、2.75、50.6%、23.1%、1.24

## 2. 晋级命令（标准流程）

```powershell
# 1) 停 A/B 守夜人（停止交替，避免与单策略守夜人抢房间）
Stop-Process -Id <AB_KEEPER_PID> -Force
Set-Content -LiteralPath "D:\hangzhouMaj\var\.keeper_ab.lock" -Value "0" -Encoding utf8

# 2) 确认当前批次自然结束（不要中途杀 run_bot，避免丢局）
#    等 var/_run_*.out 出现「完成 N 房，退出」

# 3) 用单策略守夜人接管（speedtugc，每批 12 房）
Start-Process -FilePath "python" -ArgumentList "-X","utf8","-u","var/_keeper.py","speedtugc","12" `
  -RedirectStandardOutput "D:\hangzhouMaj\var\_keeper_stdout.out" `
  -RedirectStandardError "D:\hangzhouMaj\var\_keeper.err" -WindowStyle Hidden `
  -WorkingDirectory "D:\hangzhouMaj"
```

## 3. 回滚（若真机表现变差）

```powershell
Stop-Process -Id <KEEPER_PID> -Force
Set-Content -LiteralPath "D:\hangzhouMaj\var\.keeper.lock" -Value "0" -Encoding utf8
Start-Process -FilePath "python" -ArgumentList "-X","utf8","-u","var/_keeper.py","speedtug","12" ...
```

（`bot/speedtugc.py` 与 `run_bot.py` 的注册项**保留**，随时可切回或再 A/B。）

## 4. 不晋级的情形

若 8–12 房/臂后机制指标未复现（听牌/胡未领先）→ 记录到 `queue.md`，
把「C045 在真机无效」写进 HANDOFF（并注明 sim 强场口径的迁移性存疑），回到 speedtug 跑量。
