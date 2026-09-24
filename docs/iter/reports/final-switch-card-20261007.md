# 10/7 最终换臂与比赛准备卡（用户指令：10/7 换上最屌的模型）

## 你不用做任何事（全自动）

| 时间 | 自动发生 | 产物 |
|---|---|---|
| **10/7 09:00** | 停 A/B（等对局自然结束）→ 把测试房策略换成最终臂 | `var/_switch_final.log`、`var/.final_installed` |
| 10/7 10:30 | 最终就绪校验（7 项） | `var/_final_ready_check.out`、`var/.FINAL_READY` 或 `.FINAL_NOT_READY` |
| 10/8 09:00 | 同上（提交前最后一次） | 同上 |

## 它会检查什么（任一 FAIL 就写 `.FINAL_NOT_READY`，内容写明差哪项）

1 最终臂已选定（`var/.final_arm.txt`）、
2 已注册且可实例化、
3 已真换上（`var/.final_installed`）、
4 正在跑的策略 == 最终臂、
5 役已收口（无 `.ab_mode`，不会再被 A/B 改掉）、
6 git 干净且本地 == origin/main、
7 `var/_prepare_submission.ps1` 检查 rc=0（提交物合规）。

## 出了 FAIL 怎么办（一条命令一条命令来）

```
python -X utf8 var/_final_ready_check.py          # 重看报告
Get-Content var\_final_ready_check.out -Tail 20    # 看具体 FAIL 行
python -X utf8 var/_switch_final.py --dry-run      # 看换臂将做什么（不执行）
python -X utf8 var/_switch_final.py --go           # 真换（未选定最终臂/官方模式在位会拒绝）
```

典型 FAIL：① 忘写最终臂 ⇒ 10/5–10/6 选臂后写入 `var/.final_arm.txt`；
② 步骤 7 FAIL（文案 v35 / 代码 v34）⇒ 跑 `python -X utf8 var/_apply_p0_404.py --go` 后重跑校验。

## 最后一步（10/8 12:00 前）

```
powershell -NoProfile -File var/_prepare_submission.ps1        # 先看检查
powershell -NoProfile -File var/_prepare_submission.ps1 -Go    # 真准备 + git add -f
git commit && git push                                          # 提交仓就是跑着的份
```

---

## ★ 追加（R1444）：第 4 项口径升级 + 为什么 10/7 原来会**静默失败**

> 上文"它会检查什么"里的 **第 4 项已升级**，其余不变。

- **第 4 项现在是**：「`_keeper_strategy.txt` == 最终臂 **且 `var/.rate_guard_off` 已在位**」。
  原因：`tools/rate_guard.py` 在 **A/B 收口后、`.official_mode` 未写时**生效，
  **最近 40 房净胜 < −40/房 ⇒ 会把 `_keeper_strategy.txt` 回退成 `speedtugc`**（快档：6 房 < −150）。
  10/7 换臂后正好落在这个窗口 ⇒ 最终臂可能**装上几分钟就被改掉**，而 10:30 的验收只会看到"第 4 项 FAIL"，
  看起来像"没装上"，实际是"装上后被熔断器推翻"。⇒ `_switch_final` 现在换臂成功即写 `var/.rate_guard_off`。
- **另一处已修（原来会让换臂直接失败）**：`_switch_final` 原来要等 `_keeper.py` 也退出，但 watchdog 在非 A/B 模式下
  **每 90 秒就会把 keeper 拉回来**（日志实证）⇒ 25 分钟等不到 ⇒ 09:00 与 12:00 两次都会失败。
  现在改为：先写策略文件 → 杀 `_keeper.py`（只杀监督器，不碰对局进程）→ **只等对局进程**结束 → 再走 `_switch_test_strategy.py`。
- **你仍然不用做任何事**；这两处修好后 10/7 的自动换臂才真的成立。
