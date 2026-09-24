# P0（待下一切换窗口执行）：协议 v35 BREAKING —— 404 两种码必须分开处理

> 发现于 2026-09-24 06:1x（R1221）。**当前正在跑的役 2 不能改 `bot/`（红线 3）** ⇒ 本文件是**待应用的精确补丁 + 影响量化**，
> 在**役 2 判决后的切换窗口**执行（用 `var/_switch_campaign.py` 的同一窗口）。

## 1. 问题（平台 2026-09-23 发布 v35，标记 BREAKING）

`python run_bot.py --smoke` 现在报：

```
✗ BREAKING v35（2026-09-23）: 404 TOURNAMENT_GONE 具名：它与 TOURNAMENT_NOT_FOUND 共用 404
  —— 前者是「房暂时不可达」（应重试），后者是「房不存在」（应放弃）；判型必须用 body 的 code
✗ 存在本 bot 未知的 BREAKING 变更，需人工核对
```

**我们现在的实现**（`bot/protocol.py:172-188`）：只看 **404 持续时长**——首个 404 起算，**>120s 即"房间已删除/清理，退出"**，
**完全不看 body 的 `code`**。

## 2. 影响（已量化，不是理论风险）

近期 `logs/auto_*.log` 里 `run_bot` 主循环的终止原因统计：

| 终止码 | 次数 | 按 v35 语义 | 我们的处理 | 判定 |
|---|---|---|---|---|
| **`404 TOURNAMENT_GONE`** | **10** | **房暂时不可达 ⇒ 应重试** | 持续 120s 后**退出** | ❌ **10 次错误放弃** |
| `404 TOURNAMENT_NOT_FOUND` | 8 | 房不存在 ⇒ 应放弃 | 退出 | ✅ 正确 |

⇒ 每次错误放弃 = **丢掉一个已开始的房**（约 15 分钟窗口 + 该房不在战役样本里）；
在 10/7 正式赛里，等价于**对局中途无故退出**（可能直接丢那一场分数）。

## 3. 精确补丁（两处，均已勘察）

### (1) `bot/protocol.py` —— 404 分支按 `code` 分流

把现有 172~188 行的分支替换为：

```python
            if e.status == 404:
                # ★ v35（2026-09-23 BREAKING）：404 分两种，**必须看 body 的 code**
                #   TOURNAMENT_NOT_FOUND = 房不存在 ⇒ 放弃（退出）
                #   TOURNAMENT_GONE      = 房暂时不可达 ⇒ **必须重试**（不得按持续时间判死）
                #   （其它/无法解析的 code：保守地当作瞬态重试，只记日志）
                code = (e.code or "")
                if code == "TOURNAMENT_NOT_FOUND":
                    log("锦标赛详情 404 TOURNAMENT_NOT_FOUND —— 房间不存在，退出")
                    raise
                now404 = time.time()
                if last_404_at == 0.0:
                    last_404_at = now404
                log("锦标赛详情 404 %s（暂时不可达，已持续 %.0fs），2s 后重试…",
                    code or "(无 code)", now404 - last_404_at)
                time.sleep(2)
                continue
```

（`ApiError.code` 已由 `bot/api.py::ApiError._parse_code` 从 body 解析，无需改协议解析层。）

### (2) `bot/__init__.py` —— 登记已处理的 BREAKING 版本

- `GUIDE_VERSION_KNOWN = 34` → **`35`**；
- 并在上方 BREAKING 注释块追加一行，写明 v35 的处理方式：
  `# v35（BREAKING 2026-09-23）：404 新增 TOURNAMENT_GONE（暂时不可达，应重试）与 TOURNAMENT_NOT_FOUND（应放弃）`
  `#   共用 404 ⇒ bot/protocol.py 改为按 body.code 分流；GONE 不限时重试。`

## 4. 验收（应用后当场可验）

```powershell
python run_bot.py --smoke        # 期望：冒烟结果 = 全部通过（指南版本自检不再报 BREAKING）
python -m unittest discover -s tests
python -X utf8 var/_campaign_ready.py --arms <下一役臂>
```

## 5. 为什么不在本轮直接改

红线 3：**比赛期间不改 `bot/` 既有文件（只新增）**——役 2 正在跑（40/80 每臂），
`protocol.py` 是 run_bot 的主循环文件，改了会影响**在跑的对局进程语义**。
⇒ 按纪律**留到役 2 判决后的切换窗口**一次性应用（那是"停旧役、起新役"的天然窗口，`_switch_campaign.py` 会先挡住"在打对局"）。

## 6. 范围确认（本轮核对过：v35 是**唯一**缺口）

拉取门户 `/portal/api/guide/version`（当前 `version=35`，59 条 changes）并逐条核对 **v26–v35**：

| 版本 | 级别 | 内容 | 我们的状态 |
|---|---|---|---|
| **v35** | **breaking** | 404 `GONE`/`NOT_FOUND` 分型 | ❌ **待修（本文件）** |
| v34 | added | 今日榜新增 `last` 键 | ✅ 无关（只读 `top`/`me`） |
| v33 | changed | 杠后补牌不再自动结算（可 hu/续杠/弃胡打财神续飘） | ✅ 已在案（`tests/test_speedc141.py::test_v33_gang_then_piao_chain`） |
| v32 | changed | 杠爆在杠动作时重算（fan 2 → 4） | ✅ 已在案（journal:2257） |
| v31 | changed | 局间 5 秒停顿（`phase=settled`） | ✅ 已在案（`[openwatch]` 探针 + 离开 settled 才继续） |
| v30 | changed | 他人真名收口（回退 AI 昵称 / user_id） | ✅ 无关（我们只读 user_id） |
| v29 | breaking | 全服开关可关自由匹配/自建房（403 FEATURE_DISABLED） | ✅ 已在案（GUIDE_VERSION_KNOWN=34 时评注） |

⇒ **`GUIDE_VERSION_KNOWN` 现在只需 34 → 35**，且**只有 404 这一处代码要改**——范围小、风险低、可当场验收。

## 7. ★ 一键落地器（推荐用这个，别手工改）

```powershell
python -X utf8 var/_apply_p0_404.py --check    # 只检查（不动文件）
python -X utf8 var/_apply_p0_404.py --go       # 真写盘 + 自动跑 run_bot.py --smoke 验收
```

为什么用落地器而不是 `patch`：`bot/protocol.py` 是 **LF**、`bot/__init__.py` 是 **CRLF**
⇒ 统一 diff 补丁会因行尾不匹配 apply 失败（实测）。落地器**按字节精确替换**，行尾/编码都不受影响，
并内置两处锚点校验（找不到就报错、绝不半改）。

**实测**：`--check` 通过 —— `protocol.py` 404 分支可替换（15,812 → 15,903 字节）、`__init__.py` 版本号 34→35 可替换。

## 8. 当前官方就绪状态（权威门禁）

`python tools/preflight.py` ⇒ **NOT READY**，唯一红灯就是本 P0：

```
[06:15:04] 服务器指南 v35（本 bot v34）
[06:15:04] ✗ 未知 BREAKING: 404 TOURNAMENT_GONE 具名：…
[06:15:05] ✓ fan-calc 抽样 6 例全部一致（含 3 例 v21 边界）
[06:15:08] ✓ 引擎单测通过
[06:15:12] ✓ 决策延迟健康（p99=47ms，超窗口 0 条；窗口 1s/3s）
[06:15:13] ✓ 自愈链根节点就绪（计划任务 Ready，LastTaskResult=0，Missed=0）
[06:15:13] 体检结果: NOT READY
```

⇒ **修完这一条，preflight 应当恢复 READY**（其余 4 项已全绿）；这也是**任何官方 run 前的硬门槛**。

## 9. 隔离副本验证结果（2026-09-24，R1225/R1227）——**四道全绿**

在 %TEMP%\p0verify_*（代码目录副本）里应用本补丁后：

| # | 验证 | 修前（工作区） | 修后（副本） |
|---|---|---|---|
| 1 | 补丁可干净应用 | — | ✅ _apply_p0_404.py --check |
| 2 | 
un_bot.py --smoke | ✗ 存在失败项 | ✅ **全部通过** |
| 3 | 	ools/preflight.py | **NOT READY** | ✅ **READY** |
| 4 | 目标测试（protocol/engine/hu/fan/official_guard/replay_guard） | — | ✅ **42 tests OK** |

附带修掉一处**测试脆弱性**：	est_official_guard.test_starts_with_spec_argv 原先未 mock 新增的
spec_freshness() ⇒ 结果取决于工作区 spec 是否新鲜（跨机器/12 小时后会红）；现已显式 mock，两边一致。
