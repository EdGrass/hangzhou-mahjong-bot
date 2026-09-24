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
pwsh -NoProfile -File var/_prepare_submission.ps1          # 先看检查：应 rc=0（三道门全绿：泄密 / **文案↔代码版本** / 闭包）
pwsh -NoProfile -File var/_prepare_submission.ps1 -Go     # git add -A + **4 个模型 + 37 个运行期脚本**（均 git add -f）
git status --short                                        # 确认模型 4 个 + var/ 脚本都在暂存区
python -X utf8 -m unittest tests.test_submission_closure  # ★ 闭包门：清单内文件必须全部已入仓（R1345）
git commit -m "submit: 完整可运行源码 + 4 个模型权重 + 参赛说明"
git push origin main
```

> ★ **R1345 教训**：`var/` 被 .gitignore 忽略，而**整条“接入官方平台”的链都在 var/ 里**。
> 只 `git add -f` 模型（旧做法）会导致判官 clone 后**只能跑 run_bot.py，进不了比赛流程**。
> ★ **另有一道文案门（R1356）**：`_prepare_submission.ps1` 会比对“申报正文声称的 `GUIDE_VERSION_KNOWN`”与 `bot/__init__.py` 里的，
> **不一致就 rc!=0** —— 也就是说：**没落 P0 v35 补丁就提不了交**（这是有意的硬门，不是 bug）。
> 现在强制 add 的是 **37 个 = 25 个 .py + 12 个 .ps1**，并且 `tests/test_submission_closure.py` 会堵住
> “清单引用了清单外的 var/ 文件”（依赖闭包）与“清单里的文件还没入仓”两种漏洞。

## 2. 从公网克隆验证（~判官视角，~3 分钟）

```powershell
cd $env:TEMP; git clone https://github.com/EdGrass/hangzhou-mahjong-bot hm_verify; cd hm_verify
pip install -r requirements.txt
python -X utf8 run_bot.py --smoke           # 打了 P0 后应为「冒烟结果: 全部通过」
python -X utf8 -c "import importlib.util,sys;[ (lambda sp: (lambda m: (sys.modules.__setitem__(n,m), sp.loader.exec_module(m)))(importlib.util.module_from_spec(sp)))(importlib.util.spec_from_file_location(n,p)) for n,p in [('_ensure_all','var/_ensure_all.py'),('_official_guard','var/_official_guard.py'),('_watchdog','var/_watchdog.py'),('_ab_driver','var/_ab_driver.py'),('_feature_mode','var/_feature_mode.py')] ]; print('ENGINE CHAIN IMPORT OK')"
python -X utf8 -m unittest discover -s tests
```

> ★ 上面那条 import 检查是 **R1345 的新课目**：`var/_ensure_all.py` 依赖 `var/_feature_mode.py`，
> 漏入仓时会报 `ModuleNotFoundError`，而**本机因为 var/ 什么都有、永远不会发现**。

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
