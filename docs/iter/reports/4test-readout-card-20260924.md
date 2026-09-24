# 四测读数卡（2026-09-24，`t_6266386bfd56`）

- 赛制（实拉 14:2x）：`M=10 / Rounds=16 / BaseScore=1 / YouCaiBiKao=false / OnlineConfirm=true / Kind=""`，
  `StartAt=2026-09-24 16:00`（报名截止 15:00）；开赛前 `registered=96 / ready=24`。
- ⚠ **口径**：训练基线是 `Rounds=8` ⇒ 四测的 **分/房要 ÷2** 才能同尺度比；
  率类（和牌率/听牌率/胡率/第一率）与 **分/轮不用换算**。
- ⚠ **赛事视角数据赛后会没**：实测三测 `GET /api/tournaments/t_069a55e84b26` → **404**（门户列表里也已消失），
  但单场复盘 `GET /portal/api/games/<gid>/events` 仍 200 ⇒ **全榜与 gid 清单过期即失，靠下面三个任务在赛中抢下来**。

## 赛中（全自动，不用动手）

| 时间 | 计划任务 | 产物 |
|---|---|---|
| 15:00–19:45 / 10min | `HangzhouMaj4TestFormatWatch` | `var/format_history.jsonl`、`var/_4test_format.out` |
| 15:00–19:45 / 10min | `HangzhouMaj4TestDetailSnap` | `var/4test_detail.jsonl`（ranking 全榜 + `my_games`） |
| 16:30–00:30 / 30min | `HangzhouMaj4TestReplayFetch` | `var/replays/4test_rooms/<gid>.json` |
| 19:00 / 21:00 / 22:30 / 00:30 | `HangzhouMajAfter4Test*` | 退官方模式 + **按原窗口**恢复役 2 |

## 赛后 4 步（照抄）

1. **名次 / 分数 / 分布**（本地台账，不联网）
   `python -X utf8 var/_4test_watch_detail.py --report`
   看四件事：① 我方名次与 percentile；② **正分/负分人数**（“很多房只有一个人正分”是否属实）；
   ③ 前 5 名分数与 `games_played`（进度差）；④ `stage/qualified` 是否出现（决定目标函数 E[分] 还是 P(晋级)，§V.153）。
2. **官方复盘是否补齐**
   `Get-Content var\_4test_replayfetch.out -Tail 20`（期望 `完成：新增 N，已存在 M，失败 0`；失败就重跑同一命令，工具幂等）
3. **我们 vs 同席强手（分/轮、番/胡、副露/轮）**
   `python -X utf8 tools/hu_gap_split.py 0 --dirs 4test_rooms`
   ⚠ 分/房先 ÷2 再比；率类直接用。
4. **回到役 2 判词**（四测期间 A/B 暂停，19:00 自动恢复）
   `python -X utf8 var/_gate2.py --since "2026-09-23 03:13:44" --baseline speedc151 --candidate speedvalue --mechanism pairs --min-rooms 80`
   读卡：`docs/iter/reports/yaku2-verdict-readcard.md`（四种分支 + `_bsegment.py` 一键切换）。

## 红线

四测期间**不动** `bot/`、不重启 A/B、不手工挂客户端；
19:00 后先看 `var/_after_4test.out` 确认役 2 已恢复，再做上面的读数。
