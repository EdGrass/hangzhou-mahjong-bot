# 役 2 判词判读卡（到点直接照做）

> 作用：役 2 的判词会在**夜里自动落盘**（`HangzhouMajVerdictWatch` 每 10 分钟一次，到 80/臂 起判）。
> 本卡把“在哪看、怎么读、四条分支各自该跑什么”写死，避免深夜临场想。
> 本轮口径：`since=2026-09-23 03:13:44`；基线 `speedc151`；候选 `speedvalue`；主+副各 z≥1.50；各 ≥80 房；覆盖 ≥70%；役盒 **120 房/臂**。

## 1. 在哪看

| 产物 | 说明 |
|---|---|
| `var/_verdict_役2.txt` | 判词正文（头行：第 N 次·时间·各臂房数·是否“达役盒”） |
| `var/_verdict_watch.log` | 每次判词的一行摘要（追加） |
| `var/.verdict_done_役2` | **出现 = 已出决定性判词**（不再重跑） |
| `var/.verdict_last_役2` | 内容 `N attempt`：上次判词时的房数与第几次 |

手跑一次（只读）：
```powershell
python -X utf8 var/_verdict_watch.py --label 役2 --since "2026-09-23 03:13:44" --baseline speedc151 --candidate speedvalue --mechanism pairs --check-only
```

## 2. 四条分支 → 动作

| 判词 | 含义 | 动作 |
|---|---|---|
| **ADOPT speedvalue** | 主+副均 z≥1.50 且同向、护栏过 | **起役 3**（下方 B 段） |
| **UNDECIDED** | 房数够但 z 不足 | **继续攒房**（看护每 +10 房自动重判）；到 **120 房/臂** 会标“已达役盒” |
| **达役盒**（标在判词里） | 到 120/臂 仍不决定 | 按 **§V.66/§V.67 破平序列**收口：① 强手房分/房（`var/_pick_arm.py --since "2026-09-23" --min-rooms 30`）；② 不可区分 ⇒ 两半 Pareto（`tools/hu_gap_split.py --by-arm` + `var/_seat_h2h.py --by-arm --top 32`）；③ 第1率；④ 最近判词；⑤ 保持现状 |
| **REJECT** | z≤−1.50（很不可能） | **人工重排**（§V.98：V 轴**无法**孪生到 c151）；默认仍以 speedvalue 为役 3 基线，除非明确决定重排 |
| **REFUSE（护栏/机制未过）** | 例：第1率低于基线、机制不同向 | 本役不采用；按 §V.66/§V.67 收口后进下一役（部署仍用现有生产臂） |

> 当前参考读数（48/臂，09:40）：和牌率 **z=+1.38、番 z=+1.00**（主过、副未过）；第1率 25.0% vs 17.0%；
> 强手房 −35.5 vs −39.5；台账净胜 +42.8/房（t=1.05）。**番端点是真正瓶颈**（按 t∝√n 估计需 ≈ 83 房/臂）。

## 3. B 段（仅在 **ADOPT** 时跑）——三步，约 25 秒

**前提**：役 2 已结束判定。这里不再选臂，只执行已预登记的三臂役。

```powershell
# ① 落 v35 P0 补丁（唯一阻塞项；先 --check 再 --go）
python -X utf8 var/_apply_p0_404.py --check
python -X utf8 var/_apply_p0_404.py --go
# ② 就绪校验（期望 READY）
python -X utf8 tools/preflight.py
# ③ 切役（三臂；它自带“无在打对局”闸门，拦住就先等一局自然打完再跑）
python -X utf8 var/_switch_campaign.py --baseline speedvalue --candidates speedvaluebc,speedvaluebaotouv5 --bundles speedvalue --go
# ④ C 段：注册两对判词看护（-Since 用③打印的“起役时间戳”，逐字一致）
pwsh -NoProfile -File var/_register_campaign3_watches.ps1 -Since "<起役时间戳>" -Go
```

**顺序与抢窗口（实测口径）**：
1. `tools/ab_ctl.py stop`（**只停驱动**）→ 在打的那一房自然打完（绝不强停）；
2. 等 `run_bot`/`match_super`/`_ab_driver` 都消失 → **立刻**跑上面的 ②/③（watchdog 每 90s 可能拉回 keeper，拉回就等它那一批打完再试）；
3. 注意：`_switch_campaign` 的 `--go` 会再调一次 `ab_ctl stop`（幂等），并在启动时写入新的 `.ab_mode`。

**红线**：绝不强停在打对局；一账号一房；不改预登记阈值；不改 `bot/` 既有文件（除注册表项/新增文件）。

> ★ 派生结论（本轮核实）：**正式赛那一次的切换不存在这个竞态** —— `_switch_to_official.ps1` 在**第二步**就写 `.official_mode`，
> 而 `_watchdog.py` 在官方模式下**不启不杀任何进程**（已核）⇒ 等待房结束的期间不会被带走。本卡第 3 段的抢窗口只对**役间切换**有效。
