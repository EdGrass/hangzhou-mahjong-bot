# 10/10 正式赛 · **当天操作单**（一屏版）

> 正式赛 **10/10 19:30**。本卡只列“今天该做什么”；完整手册见 `competition-runbook-20260923.md` §8。

## 1. 必须由你做的（**最迟 18:00**）

把**当天的赛事令牌**保存为 `var/.token_final_20261010`（纯令牌文本、无换行也行）。
缺它 ⇒ 18:50 的上线会 **fail-closed 拒绝**（宁可不上也不猜）。（就绪校验第 8 项会在 10/7、10/8、10/9 提醒）

## 2. 自动发生的（不用动手）

| 时刻 | 任务 | 做什么 |
|---|---|---|
| **18:50** | `HangzhouMajFinalEventSwitch` ⇒ `_final_event_switch.py --go` | 读 `.final_arm.txt` 的臂 + 令牌 → 门户解**唯一 registering 赛事 id** → 调 `_switch_to_official.ps1`（**不传** `-AllowNotReady`）⇒ 写 `.official_mode` + 拉起 keepalive |
| **19:25** | `HangzhouMajFinalEventReady` ⇒ `_final_event_ready.py` | T-5 保险：若 `.official_mode` 不在 ⇒ **先重试上线**再补 `/ready`；仍不在 ⇒ 落 `.EVENT_SWITCH_BLOCKED` |

（两台都是 `pythonw.exe`，工作目录 = 仓库根；参数输入都已复核✓）

## 3. 赛前两分钟自查（可选，只读）

```powershell
python -X utf8 tools/tminus_check.py --strategy (Get-Content var\_keeper_strategy.txt) ``
    --token-file var/.token_final_20261010
python -X utf8 var/_final_event_ready.py --dry-run     # 看 19:25 那台将做什么（不落标记）
```

（注：如果此时还没拿到令牌，上面第一条会报“读不到”，不必惊讶。）

## 4. 若 18:50 / 19:25 失败：看一个文件、照拄一条命令

```powershell
Get-Content var\.EVENT_SWITCH_BLOCKED          # 它已写好：差什么 + 可直接照拄的命令
python -X utf8 var/_switch_to_official.ps1 -Strategy <最终臂> -TokenFile var/.token_final_20261010 -TournamentId <tid>
```

- `<最终臂>` 取 `var/.final_arm.txt`；`<tid>` 取门户当前 registering 赛事。
- **逃生阀纪律**：`-AllowNotReady` **只**在 preflight 因「**未知 BREAKING**」卡住、  且已人工确认该变更对我们无害时才加；**绝不自动使用**。

## 5. 赛中

- `OfficialGuard`（每 60 秒）自动看护；若 `.official_mode` 在位但 **keepalive 与 run_bot 都不在跑**、且 `_official_guard.log` 末 3 行有 `⚠`/`✗`
  ⇒ 心跳会**立刻报你**（R1537）；
- **被淘汰后** keepalive“起了又退”是**正常**的（日志写的是 `✓` 而不是 `⚠`）。

## 6. 赛后

```powershell
python -X utf8 var/_exit_official.py
```

## 7. 今天别做

- 不改 `bot/`；**不再动** `.final_arm.txt`（今天不换臂）；不手搓状态文件。
