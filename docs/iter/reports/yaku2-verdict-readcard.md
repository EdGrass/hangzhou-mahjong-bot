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

> **参考读数会随房数移动（以当时判词为准）**。最近一次实测（**110 房、各 55**，`_gate2 --mechanism pairs`）：
> 主端点 和牌率/房 **+0.64（z=+0.55）**、副端点 番/房 **+1.37（z=+0.85）**；机制 pairs（>=3对占比）+16.32（z=+7.48）PASS；护栏第1率 20.4% vs 25.5% PASS。
>
> ★ **功率预算（R1351，决定“到役盒怎么办”）**：z 随 √n 缩放 ⇒ 若效应量不变，到 **120 房/臂** 时主/副端点仅 **z≈+1.27 / +1.21**；
> 要在端点上判死需 **~167 / ~185 房/臂**（按 ~1.5 房/h 是 4 天+，会吃掉役 3/4/5 排期）。
> ⇒ **“到役盒转两半 Pareto 破平”是预期路径，不是异常**；**不要为追端点 z 而延长役盒**。

## 3. B 段（仅在 **ADOPT** 时跑）—— **一键优先，四步为备**，约 25 秒

**前提**：役 2 已结束判定。这里不再选臂，只执行已预登记的三臂役。

### 3a. 推荐：一键（`var/_bsegment.py`，R1341，**默认 dry-run**）

```powershell
python -X utf8 var/_bsegment.py            # dry-run：只打印计划、不动 A/B
python -X utf8 var/_bsegment.py --go       # 真执行
```

它依次做：`停驱动（等自然结束）→ 等空档 → P0 补丁 → preflight → 切役（自动解析起役时间戳）→ 注册两对看护`。
**奠基：它把“两对看护共用同一个解析结果”写死了**（R1341 当年的 bug 就是手抄时间戳不一致）。

### 3b. 备用：手动四步（逐条已验证）

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

> ★ 窗口内**顺带做一件事**：此时无对局 ⇒ 跑一次
> `python -X utf8 -m unittest discover -s tests`（全量单元测试）+ `python -X utf8 run_bot.py --smoke`
> 作为**提交前证据**。为什么要在窗口：R1182 已用 1,485 个提交延迟样本证明
> **A/B 期间跑全套单测会真的抬高提交延迟（p99 2.8s、丢动作）**，所以这件事只能在窗口做。

**顺序与抢窗口（实测口径）**：
1. `tools/ab_ctl.py stop`（**只停驱动**）→ 在打的那一房自然打完（绝不强停）；
2. 等 `run_bot`/`match_super`/`_ab_driver` 都消失 → **立刻**跑上面的 ②/③（watchdog 每 90s 可能拉回 keeper，拉回就等它那一批打完再试）；
3. 注意：`_switch_campaign` 的 `--go` 会再调一次 `ab_ctl stop`（幂等），并在启动时写入新的 `.ab_mode`。

**红线**：绝不强停在打对局；一账号一房；不改预登记阈值；不改 `bot/` 既有文件（除注册表项/新增文件）。

> ★ 派生结论（本轮核实）：**正式赛那一次的切换不存在这个竞态** —— `_switch_to_official.ps1` 在**第二步**就写 `.official_mode`，
> 而 `_watchdog.py` 在官方模式下**不启不杀任何进程**（已核）⇒ 等待房结束的期间不会被带走。本卡第 3 段的抢窗口只对**役间切换**有效。


## 4. 下一步（役 3 判词后）

役 3（BC+V）判词一出，**役 4 的臂直接查表**（四格均已就绪：注册 + 同名单测 + **有效**预登记）：

| 役 3 判词 | 新基线 | 役 4 实际臂 | 预登记 |
|---|---|---|---|
| BC✓ V✓ | `speedvaluebc` | `speedvaluebcmeldp45` | campaign4b |
| BC✓ V✗ | `speedvaluebc` | `speedvaluebcmeldp45` | campaign4b |
| BC✗ V✓ | `speedvaluebaotouv5` | `speedvaluebaotouvmeld` | campaign4c |
| BC✗ V✗ | `speedvalue` | `speedvaluemeldp45` | campaign4 |

（详见 plan §V.49 / §V.139；BC 分支实际用的是**剂量档** `speedvaluebcmeldp45`。）

## ★ 第一率旁证（R1348，**不是判据**）

```powershell
python -X utf8 tools/first_rate_readout.py          # 自动取本役臂与 since
```

判据仍是 `_gate2.py`；第一率只作**方向/护栏**。原因（工具会直接算）：一房只贡献 1 个名次 ⇒
要分辨 **5.4pp** 的第一率差需要**每臂 ~496 房**，本役盒只有 **80 房/臂** ⇒ **功率不够**。
`_gate2` 用复盘的和牌率/番（样本量 = 局数）⇒ 功率高一个量级。
