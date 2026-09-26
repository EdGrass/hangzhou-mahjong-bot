# 10/7 最终换臂与比赛准备卡（用户指令：10/7 换上最屌的模型）

## 自动部分（你不用动手）—— 但**有两件人工事**（见检查项 8/9）

| 时间 | 自动发生 | 产物 |
|---|---|---|
| **10/7 08:30** | 自动定臂（只叠**已判正**的层；人工已写 `var/.final_arm.txt` 则 no-op） | `var/_final_arm_confirm.txt` |
| **10/7 09:00** | 停 A/B（等对局自然结束）→ 把测试房策略换成最终臂 | `var/_switch_final.log`、`var/.final_installed` |
| 10/7 10:30 | 最终就绪校验（**9 项**） | `var/_final_ready_check.out`、`var/.FINAL_READY` 或 `.FINAL_NOT_READY` |
| 10/7 12:00 | 换臂重试（若 08:30 后才出判词 ⇒ 补装更深已判正层） | `var/_final_switch_retry.log` |
| 10/8 09:00 | 就绪校验（提交前） | 同上 |
| 10/8 10:00 | 自动提交（门禁 → add -f → commit → push → 校验） | `var/.final_submitted` |
| **10/8 11:00** | **提交重试**（幂等；10:00 若瞬时失败） | 同上 |
| 10/9 09:00 | 就绪校验（T-1） | 同上 |

## 它会检查什么（任一 FAIL 就写 `.FINAL_NOT_READY`，内容写明差哪项）

1 最终臂已选定（`var/.final_arm.txt`）、
2 已注册且可实例化、
3 已真换上（`var/.final_installed`）、
4 正在跑的策略 == 最终臂、
5 役已收口（无 `.ab_mode`，不会再被 A/B 改掉）、
6 git 干净且本地 == origin/main、
7 `var/_prepare_submission.ps1` 检查 rc=0（提交物合规）。
8 **10/10 的令牌已在位**（`var/.token_final_20261010`）—— **人工输入**：若平台尚未发牌属预期，
  但最迟 **10/10 18:00** 前必须放好（否则 18:50 上线会 fail-closed）；
9 **申报页已提交**（人工收据 `var/.SUBMITTED_FORM`）—— **人工输入**：10/8 12:00 前把
  `docs/申报正文-最终.md` 正文 + 仓库链接交到申报页（机器只能推仓）。

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

## ★ 更新（R1448）：最后一步**已自动化**（10/8 10:00）

上面"最后一步（10/8 12:00 前）"的三步现在由计划任务 **`HangzhouMajFinalSubmit` @ 10/8 10:00** 自动执行：
检查（门禁，fail-closed）→ `-Go`（add -f + commit）→ `git push`（非交互，已实测凭据可用）→ 校验"工作区干净 且 本地==origin/main"
→ 写 `var/.final_submitted`。任一条不过 ⇒ **不提交、不推送**，并写 `var/_submit_final.out`（不静默）。

- 手动重跑：`python -X utf8 var/_submit_final.py --go`（先 `--dry-run` 只看门禁）；日志 `var/_submit_final.log`。
- 前提：`var/_prepare_submission.ps1`（只检查）rc==0 —— 它要求**文案 v35 == 代码 v35**，
  而 v35 补丁由役 3 起役时的 B 段自动落盘（10/7 前早已完成）。
- 所以 10/8 那天**仓库部分不需要你动手**；但人工输入**有两项**：
**（a）** 10/10 的令牌文件 `var/.token_final_20261010`；**（b）** 10/8 12:00 前的**申报页提交**（正文 + 仓库链接）。
★ 两项都已有检查项（第 8 / 第 9），失败会写 `.FINAL_NOT_READY` 并由心跳转述。
★ 且 10:00 提交若失败，**现在会写 `.FINAL_NOT_READY`（不再静默），11:00 还有一次自动重试**。
