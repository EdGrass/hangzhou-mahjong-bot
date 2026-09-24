# 提交日卡片（10/8 12:00 截止）—— 直接照做

> 官方公告（门户 `GET /portal/api/announcements`）：**提交截止 10 月 8 日 12:00**；
> **正式比赛 10 月 10 日 19:30**；提交入口 = 易网-荣誉-AI 大赛专区
> `https://e.netease.com/honor/1000042?awardId=150297`。提交内容 **2 项（缺一不可）**：① 使用说明；② 完整可运行源码。

## 0. 前提（应在 10/7 就已满足）

- [ ] **v35 P0 补丁已落地并已 push**（役间 B 段做：`_apply_p0_404.py --go` → `preflight` → `_switch_campaign`）
- [ ] **最终臂已定并写入** `var/_keeper_strategy.txt`
- [ ] **该臂的模型/文件都在仓库里**（R1327 查过 13/13 在已追踪集合；模型 4 个已 `git add -f`）

## 1. 冻结并推送（~5 分钟）

```powershell
cd D:\hangzhouMaj
git status --porcelain                     # 应为空（或只有你刚改的东西）
pwsh -NoProfile -File var/_prepare_submission.ps1 -Go     # git add -A + git add -f 四个模型
git status --short                                        # 确认模型四个都在暂存区
git commit -m "submit: 完整可运行源码 + 4 个模型权重 + 参赛说明"
git push origin main
```

## 2. 从公网克隆验证（~判官视角，~3 分钟）

```powershell
cd $env:TEMP; git clone https://github.com/EdGrass/hangzhou-mahjong-bot hm_verify; cd hm_verify
pip install -r requirements.txt
python -X utf8 run_bot.py --smoke           # 打了 P0 后应为「冒烟结果: 全部通过」
python -X utf8 -m unittest discover -s tests
```

> 若没打 P0：smoke 会因 v35 而报「存在失败项」（R1325 已证打了就全绿）⇒ 不要在这个状态下提交。

## 3. 易网提交（简单但不能漏）

1. 登录 `https://e.netease.com/honor/1000042?awardId=150297`
2. **正文**：粘贴 `docs/申报正文-最终.md` **全文**（已含仓库链接 + 依赖表 + 4 个权重说明）
3. **源码**：优先用**仓库链接**；若要附件则压包含 `.git` 的目录（注意：本仓 `.git` 已 **18.6MB**，压完可能超 20MB 线 ⇒ 仓库链接更稳）
4. 提交后**回看一遍**：两项（说明 + 源码）都在，仓库链接可匿名打开。

## 4. 红线与注意

- 第 2 步的全量单测**会抬高提交延迟**（R1182）⇒ 尽量在**无对局窗口**或对往上役无损的时刻跑；不并发。
- **10/8 12:00 后不再动可上场的臂/模型**（评委那边的快照已固定）；之后只做"**选哪个已提交的臂**"的决定。
- 10/10 19:30 正式赛前：用户登录杭麻平台**领取事件令牌** → `_format_fidelity.py --tid <正式赛 tid>` → 支付与否则同四测的三段式（§V.90）。
