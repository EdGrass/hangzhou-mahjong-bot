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
