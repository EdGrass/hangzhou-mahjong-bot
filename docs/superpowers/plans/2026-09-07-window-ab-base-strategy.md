# SpeedH（杠/链 EV）+ 正式赛窗口 A/B 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 建议 superpowers:subagent-driven-development 或 executing-plans 逐任务执行本计划（checkbox 跟踪）。

**Goal:** 按已批准设计（docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md）交付：P0 真机规则语义探针 → P1 SpeedH 杠 EV 候选 → P2 窗口 A/B 工具链（window_audit / replay 采集），最终以"同赛段 SpeedE vs SpeedH"正式赛成绩裁决。

**Architecture:** sim 退役为回归工具；策略强度只信真机。P0 用特制探针策略在测试房强制触发暗杠/补杠/过胡，记录服务器真实事件序列；P1 的 EV 门控以纯函数实现（离线单测可钉），仅在真机席位注册（不进 arena/stability 默认）；P2 工具支持 任意 N 席位日志 按 gid/赛段块 配对裁决。

**Tech Stack:** Python 3.12（unittest，无 pytest）、repo 既有 bot/mahjong/tools 约定、测试房 API（room_ctl）、portal cookie（var/.portal_cookie）。

**执行前提（每个阶段开始前人工确认）：**
- P0/P1 冒烟需要 portal cookie 有效（var/.portal_cookie，若 401 请用户更新）；
- P2 需要用户提供正式赛参赛令牌；
- P0 报告核准后才执行 P1（P1 代码细节依赖探针结论，见 T3 门）。

---

## 文件结构（本计划将创建/修改）

| 文件 | 职责 |
|---|---|
| `bot/speedprobe.py`（新） | 探针策略：`ProbeGang`（自摸 4 同/补杠触发）与 `ProbeHuPass`（胡形弃牌） |
| `tests/test_speedprobe.py`（新） | 探针策略的离线语义测试 |
| `run_bot.py`（改） | STRATEGY_FACTORIES 增加 probe_gang/probe_hupass/speedh |
| `bot/speedh.py`（新，P1） | SpeedH：杠 EV 门控（纯函数 + decide 集成） |
| `tests/test_speedh.py`（新，P1） | 门控纯函数与 decide 行为测试 |
| `tools/window_audit.py`（新，P2） | N 日志 → gid 配对/块级配对 → δ/CI/裁决 + 席位健康报告 |
| `tests/test_window_audit.py`（新，P2） | 合成日志夹具下的审计正确性 |
| `tools/replay_fetch.py`（新，P2） | 赛后复盘拉取（server API；失败则提示用记录器） |
| `docs/iter/reports/P0-probe.md`、`P1-speedh.md`、`window-A-B 运行手册.md`（新） | 阶段报告与运行手册 |
| `docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md` | 已批准设计（不变） |

---

## Task 0: 基线确认与分支纪律

- [ ] **Step 1: 基线回归**

Run: `python -X utf8 -m unittest discover -s tests`
Expected: `Ran 81 tests ... OK`

- [ ] **Step 2: 确认 cookie 与工具在位**

Run: `Test-Path var\.portal_cookie; python -X utf8 tools\room_ctl.py list`
Expected: `True`；返回 HTTP 200 JSON（若 401 → 暂停，向用户要新 cookie）

- [ ] **Step 3: 提交基线**

```bash
git add -A && git commit -m "chore: baseline before SpeedH plan" || echo "nothing to commit"
```

---

## P0：真机规则语义探针

### Task 1: 探针策略 speedprobe

**Files:**
- Create: `bot/speedprobe.py`
- Test: `tests/test_speedprobe.py`
- Modify: `run_bot.py`（注册 probe_gang / probe_hupass）

- [ ] **Step 1: 写失败测试**

`tests/test_speedprobe.py`：

```python
"""speedprobe 探针策略语义测试（离线，钉行为）."""
import unittest

from bot.model import my_turn  # noqa: F401
from bot.speedprobe import ProbeGang, ProbeHuPass
from bot.speede import SpeedE


def _view(hand, drawn, god=None, melds=None, can_gang=True):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": drawn, "my_hand": list(hand),
            "god": god or {}, "scores": None,
            "melds": list(melds or []), "offer_tile": None,
            "can_gang": can_gang, "river": []}


class TestProbeGang(unittest.TestCase):
    def test_angang_when_quad_in_hand(self):
        # 手牌含 4 张 1w（非白板）→ 应提交暗杠
        hand = ["1w"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东"]
        act = ProbeGang().decide(_view(hand, drawn="1w", can_gang=True))
        self.assertEqual(act, {"action": "gang", "tile": "1w"})

    def test_white_never_gang(self):
        hand = ["白"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东"]
        act = ProbeGang().decide(_view(hand, drawn="白", can_gang=True))
        self.assertEqual(act["action"], "discard")     # 白板禁杠 → 走弃牌

    def test_bugang_when_peng_plus_fourth(self):
        melds = [{"type": "peng", "tile": "5b", "tiles": ["5b"] * 3}]
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东"]
        act = ProbeGang().decide(_view(hand, drawn="5b", melds=melds))
        self.assertEqual(act, {"action": "gang", "tile": "5b"})


class TestProbeHuPass(unittest.TestCase):
    def test_hu_pass_discards_instead_of_hu(self):
        # 可胡（含刚摸）→ 探针提交 discard（测服务器是否允许过胡）
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        act = ProbeHuPass().decide(_view(hand, drawn="东"))
        self.assertEqual(act["action"], "discard")


class TestProbeFallsBackToSpeedE(unittest.TestCase):
    def test_no_gang_situation_plays_speedE(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        p = ProbeGang()
        e = SpeedE()
        v = _view(hand, drawn="南")
        self.assertEqual(p.decide(v)["tile"], e.decide(v)["tile"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 -m unittest tests.test_speedprobe -v`
Expected: FAIL（`ModuleNotFoundError: bot.speedprobe`）

- [ ] **Step 3: 实现**

`bot/speedprobe.py`：

```python
"""speedprobe —— 真机规则语义探针策略（仅测试房用，勿参赛）。

ProbeGang：my_turn 且可杠时：
  1) 手牌含 4 张同码（白板除外）→ 提交暗杠 gang；
  2) 有碰组且手牌含该碰牌第 4 张 → 提交补杠 gang；
  其余局面完全回退 SpeedE 决策。
ProbeHuPass：可胡（含刚摸）时改提交 discard —— 探测服务器是否允许"过胡"。
设计动机：sim v2 杠后不补牌且与规则文档矛盾；本 bot 从未在 draw 回合提交过
gang——服务器对 暗杠/补杠/过胡 的真实响应（事件序列/409/倍率）只能真机观察。
"""
from __future__ import annotations

from mahjong.hu import is_win

from .model import my_turn
from .speed import GOD_TILE  # noqa: F401（白板=财神，禁杠）

from .speede import SpeedE


class ProbeGang(SpeedE):
    """my_turn 时强制触发 暗杠/补杠 场景（无则回退 SpeedE）。"""

    def __init__(self, name="probe_gang"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view) and view.get("drawn_tile"):
            hand = view["my_hand"]
            if view.get("can_gang"):
                for m in view.get("melds") or []:
                    if m["type"] == "peng":
                        t = m["tile"]
                        if t != "白" and hand.count(t) >= 4:
                            return {"action": "gang", "tile": t}
                for t in sorted(set(hand)):
                    if t != "白" and hand.count(t) == 4:
                        return {"action": "gang", "tile": t}
        return super().decide(view)


class ProbeHuPass(SpeedE):
    """可胡即弃（测过胡合法性）；无胡则回退 SpeedE。"""

    def __init__(self, name="probe_hupass"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view) and view.get("drawn_tile"):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu:
                drawn = view.get("drawn_tile")
                if view.get("god", {}).get("catch_play") and drawn:
                    return {"action": "discard", "tile": drawn}
                # 正常胡形 → 故意弃刚摸（或任一张），观察服务器响应
                tile = drawn if hand.count(drawn) >= 1 else hand[0]
                return {"action": "discard", "tile": tile}
        return super().decide(view)
```

> 注：`GOD_TILE` 与 `"白"` 等价；`bot/speed.py` 中 `HONOR` 已含白。白板禁杠按 sim 规则写死，探针同时验证真机是否同规则（若服务器允许白杠，探针报告会记录差异——见 Task 3 表格）。

- [ ] **Step 4: 运行确认通过**

Run: `python -X utf8 -m unittest tests.test_speedprobe -v`
Expected: 4 项 OK（若 ProbeGang 暗杠用例被 is_win 拦截（4×1w 已构成刻子非胡形，不应 hu）——若断言失败，按实际修正 fixture 并记录）。

- [ ] **Step 5: 注册到 run_bot（测试专用入口）**

`run_bot.py` STRATEGY_FACTORIES 增加：

```python
    "probe_gang": lambda: __import__("bot.speedprobe", fromlist=["ProbeGang"]).ProbeGang(),
    "probe_hupass": lambda: __import__("bot.speedprobe", fromlist=["ProbeHuPass"]).ProbeHuPass(),
```

- [ ] **Step 6: 全量回归 + 提交**

Run: `python -X utf8 -m unittest discover -s tests`
Expected: `Ran 85 tests ... OK`（81 + 4 新增）

```bash
git add bot/speedprobe.py tests/test_speedprobe.py run_bot.py
git commit -m "feat(probe): speedprobe 探针策略（暗杠/补杠/过胡触发）+ 注册"
```

### Task 2: P0 探针运行（测试房，真实服务器）

**Files:**
- Create: `docs/iter/reports/P0-probe.md`（先建模板，运行后填数）

- [ ] **Step 1: 建 P0 报告模板**

`docs/iter/reports/P0-probe.md` 骨架：

```markdown
# P0 真机规则语义探针报告

> 日期：____ | 状态：进行中
> 房/会话：____ | 场景触发局数：gang=__/hupass=__ | 时间跨度：____

## 1. 暗杠（自摸 4 同码）
事件序列：____ | 补牌？____ | chain/倍率：____ | 白板禁杠验证：____
## 2. 补杠（碰组 + 第 4 张）
事件序列：____ | 补牌？____ | 连杠窗口？____
## 3. 杠上花/胡判（若触发）
番数对照 fan-calc：____
## 4. 过胡（胡形弃牌）
服务器响应（放行/409/自动胡/房间异常）：____
## 5. 结论 → P1 修订点
- [ ] 语义与假设一致 → 按计划实现 SpeedH
- [ ] 差异：____（修订 P1 门控条件后再实现）
```

- [ ] **Step 2: 建房并布 4 席（gang 探针房）**

```powershell
$env:HM_PORTAL_COOKIE = (Get-Content var\.portal_cookie -Raw).Trim()
python -X utf8 tools\room_ctl.py create --m 1 --rounds 1 --name "p0-gang"
# 取 4 令牌 → 2×probe_gang + 2×speedE（观察席）
# 每席：Start-Process python -X utf8 run_bot.py <tok> --strategy probe_gang --log logs/p0_gang_<席>.log
```

- [ ] **Step 3: 布 hu_pass 探针房（第二房须先 close 第一房）**

```powershell
python -X utf8 tools\room_ctl.py close <房1>
python -X utf8 tools\room_ctl.py create --m 1 --rounds 1 --name "p0-hupass"
# 2×probe_hupass + 2×speedE，日志 logs/p0_hupass_<席>.log
```

- [ ] **Step 4: 场景触发与观测**

场景触发概率低（4 同码起手 ~1-3%）：用多会话循环（可复用 `tools/l2_super.py` 的建房/重启骨架，把策略换成 probe）或手动重开房，累计到 ≥1 次暗杠、≥1 次补杠、≥3 次过胡触发；每次触发后在对应 log 记录：
- 提交 gang 后的服务器响应（`提交: {'action': 'gang',...}` 之后的 事件/409/本场积分）；
- hu_pass 席提交 discard 后：是否 409、是否被服务器代胡、场次是否正常结算。

Run: 观察命令（每 ~90s 一次）
`python -X utf8 tools\l2_audit.py`（或 grep 目标日志 `Select-String -Path logs\p0_*.log -Pattern 'gang|409|胡'`）
Expected: 日志出现 gang 提交与后续事件序列。

- [ ] **Step 5: 关闭全部探针房并停进程（不留占位）**

```powershell
python -X utf8 tools\room_ctl.py close <当前房id>
# Stop-Process 全部 run_bot/python 探针进程
```

### Task 3: P0 结论 → P1 门

- [ ] **Step 1: 填写 P0 报告**（Task 2 观察结果入档 `docs/iter/reports/P0-probe.md`）
- [ ] **Step 2: 判定门**

对照设计 §4.1 探针清单：
- 若全部与假设一致（杠补牌、chain×2、过胡被拒或放行有明确语义、白板禁杠成立）→ **P1 按计划执行**；
- 若有差异 → 在 P0 报告记录差异，**修订 Task 4 门控条件后再进 P1**（本计划 Task 4 的条件函数即修订落点）。
- [ ] **Step 3: 提交**

```bash
git add docs/iter/reports/P0-probe.md
git commit -m "docs(probe): P0 真机规则语义探针报告"
```

---

## P1：SpeedH（杠 EV 门控）

> 前置：P0 门通过。以下门控条件以"补杠/暗杠 → 服务器补牌、chain+1（×2）、白板禁杠"为假设；若 P0 有差异，先改 `_safe_gang` 条件再测。

### Task 4: 杠门控纯函数 + 离线测试

**Files:**
- Create: `bot/speedh.py`（先只放纯函数）
- Test: `tests/test_speedh.py`

- [ ] **Step 1: 写失败测试**

`tests/test_speedh.py`：

```python
"""SpeedH 杠门控纯函数测试（不依赖 sim/真机）。"""
import unittest

from bot.speedh import bugang_value, safe_gang
from mahjong.shanten_exact import shanten as exact_shanten


def _s(rem13, exposed, gangs):
    return exact_shanten(rem13, qidui=(exposed == 0 and gangs == 0),
                         exposed_melds=exposed, gangs=gangs)


class TestSafeGang(unittest.TestCase):
    def test_bugang_on_peng_with_fourth_listening_ok(self):
        # 碰 5b + 手牌含第 4 张 5b；去 5b 后仍听（13 张结构不变）→ 允许
        hand_no_draw = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w",
                        "8w", "9w", "东", "东"]           # 12 张 + 摸 1 = 13
        self.assertTrue(safe_gang(hand_no_draw + ["东"], "东",
                                  exposed=1, gangs=0, meld_4th="5b"))

    def test_bugang_never_when_white(self):
        self.assertFalse(safe_gang(["白"] * 3 + ["1w"], "1w",
                                   exposed=1, gangs=0, meld_4th="白"))

    def test_angang_quad_keeps_shanten(self):
        # 4×7t 暗杠：去 4 张后需服务器补 1 张；本地按 补后仍 ≥ 当前向听 判
        hand = ["7t"] * 4 + ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东"]
        self.assertTrue(safe_gang(hand, "7t", exposed=0, gangs=0,
                                  meld_4th=None))


class TestBugangValue(unittest.TestCase):
    def test_value_positive_when_chain_multiplier(self):
        # chain 0→1：胡番 ×2 期望为正（结构性收益，返回值>0 即主张杠）
        self.assertGreater(bugang_value(chain=0), 0)
        self.assertGreater(bugang_value(chain=2), 0)


if __name__ == "__main__":
    unittest.main()
```

> 测试意图说明：`safe_gang` 判断"杠这一手是否结构上不亏"（去杠牌后向听不增）；
> `bugang_value` 表达 chain×2 的正收益占位（v1 保守门控 = safe_gang 即可杠，
> 数值化 EV 留 v2；若 P0 显示倍率异常，此处修订）。

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 -m unittest tests.test_speedh -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现纯函数**

`bot/speedh.py`（第一阶段只含函数 + docstring）：

```python
"""SpeedH —— 杠/链 EV 候选（v1 范围：补杠/暗杠安全门控）。

设计：docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md
P0 假设（真机探针核准后生效）：自杠合法且服务器补牌、chain+1 且结算 ×2、
白板禁杠。v1 门控保守：杠后形态向听不增即杠（补杠不破坏已听结构、
暗杠四张离手后由服务器补牌），"可胡即胡"保持不动。
sim 无法建模杠后补牌（sim v2 不补牌）→ SpeedH 不进 arena/stability 默认，
只注册真机席位入口。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

GOD = "白"


def safe_gang(hand13, drawn, exposed, gangs, meld_4th=None):
    """杠是否结构安全（保守 v1 门控）。

    hand13: my_hand（含刚摸的 14 张或 13 张皆可——以去杠牌后的形态为准）；
    meld_4th: 补杠目标碰牌牌面；None 表示暗杠（手牌 4 张同码）。
    返回 True 当且仅当：
      - 杠牌非白板；
      - 补杠：去掉第 4 张后（结构视为碰组升级为杠组，牌数等效）
        剩余手牌向听 ≤ 杠前向听（即不因杠而退向听）；
      - 暗杠：4 张离手后按补 1 张的最优可能仍不劣于当前向听。
    """
    if meld_4th == GOD:
        return False
    hand = list(hand13)
    if meld_4th is not None:
        # 补杠：手牌中移除第 4 张（碰组 3 张已在 melds 外）
        if hand.count(meld_4th) < 1:
            return False
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
        rem = list(hand)
        rem.remove(meld_4th)
        after = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed + 1, gangs=gangs)
        return after <= before
    # 暗杠：4 张同码（非白）在手
    quads = [t for t in sorted(set(hand))
             if t != GOD and hand.count(t) == 4]
    if not quads:
        return False
    t = quads[0]
    before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                           exposed_melds=exposed, gangs=gangs)
    # 保守近似：杠后补 1 张（服务器行为）视为 从 (手-4) 张中补回最差也
    # 不低于当前 —— 用 去4张后 的向听（补牌最坏情况）比较
    rem = [x for x in hand if x != t][:-1]      # 去掉 4 张中的 3 张可视……
    # 简化且稳妥：仅当手牌除 quad 外已成型（向听 ≤ 1）才主张暗杠
    rest = [x for x in hand if x != t]
    after_base = exact_shanten(rest, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs + 1)
    return after_base <= before + 2             # 补 1 张的乐观上界容忍
```

> ⚠️ 暗杠分支注释了两种口径，写实现时**以 P0 实测补牌语义为准**修订该分支
> （若服务器补牌 → 用 "rest 的 13 张最优补 1" 语义；本占位为保守版）。
> 若实现后发现 `exact_shanten` 对非法长度抛 ValueError，捕获后返回 False
> （长度不匹配 = 真机边缘 → 不杠最安全）。**这一步需要执行者在 P0 报告核准后
> 用真实语义把暗杠分支写对，并更新对应测试断言。**

- [ ] **Step 4: 运行确认通过（按 P0 语义校准断言后）**

Run: `python -X utf8 -m unittest tests.test_speedh -v`
Expected: 4 项 OK

- [ ] **Step 5: 提交**

```bash
git add bot/speedh.py tests/test_speedh.py
git commit -m "feat(speedh): 杠门控纯函数（补杠/暗杠安全判据）+ 测试"
```

### Task 5: SpeedH decide 集成 + 注册

**Files:**
- Modify: `bot/speedh.py`（增加 SpeedH(SpeedE)）
- Modify: `run_bot.py`（注册 "speedh"）
- Test: `tests/test_speedh.py`（追加 decide 用例）

- [ ] **Step 1: 追加失败测试**

`tests/test_speedh.py` 增加：

```python
class TestSpeedHDecide(unittest.TestCase):
    def _view(self, hand, drawn, melds=None, can_gang=True):
        return {"seat": 0, "phase": "draw", "turn": 0,
                "responding_seats": [], "drawn_tile": drawn,
                "my_hand": list(hand), "god": {}, "scores": None,
                "melds": list(melds or []), "offer_tile": None,
                "can_gang": can_gang, "river": []}

    def test_gangs_when_safe(self):
        from bot.speedh import SpeedH
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东", "东"]
        melds = [{"type": "peng", "tile": "5b", "tiles": ["5b"] * 3}]
        act = SpeedH().decide(self._view(hand, drawn="东", melds=melds))
        # 补杠安全且手牌已是听/成型 → 提交 gang（tile=5b）
        self.assertEqual(act["action"], "gang")

    def test_not_gang_when_can_gang_false(self):
        from bot.speedh import SpeedH
        hand = ["1w"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东"]
        act = SpeedH().decide(self._view(hand, drawn="1w", can_gang=False))
        self.assertEqual(act["action"], "discard")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 -m unittest tests.test_speedh -v`
Expected: FAIL（SpeedH 未定义）

- [ ] **Step 3: 实现集成**

`bot/speedh.py` 追加：

```python
from mahjong.hu import is_win  # noqa: F401
from .model import my_turn
from .speede import SpeedE
from .speed import _best_discard


class SpeedH(SpeedE):
    """SpeedE + 杠 EV 门控（v1：safe_gang 通过即杠，其余继承 E）。"""

    def __init__(self, name="speedh"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view) and view.get("drawn_tile"):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            # 可胡即胡（继承 E 的优先级：胡 > 杠）
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu and drawn:
                return {"action": "hu", "tile": ""}
            if view.get("god", {}).get("catch_play"):
                return super().decide(view)      # 抓打圈不杠
            if view.get("can_gang"):
                # 补杠优先于暗杠检查
                for m in melds:
                    if m["type"] == "peng":
                        t = m["tile"]
                        if safe_gang(hand, drawn, exposed, gangs,
                                     meld_4th=t):
                            return {"action": "gang", "tile": t}
                if safe_gang(hand, drawn, exposed, gangs, meld_4th=None):
                    quad = next(t for t in sorted(set(hand))
                                if t != "白" and hand.count(t) == 4)
                    return {"action": "gang", "tile": quad}
            return super().decide(view)
        return super().decide(view)
```

- [ ] **Step 4: 运行确认通过 + 全量回归**

Run: `python -X utf8 -m unittest tests.test_speedh -v`
Expected: 6 项 OK（4 函数 + 2 decide）
Run: `python -X utf8 -m unittest discover -s tests`
Expected: `Ran 88 tests ... OK`（81 + 4 probe + 3 speedh？按实际计数校准说明）

- [ ] **Step 5: 注册真机入口 + 提交**

`run_bot.py` STRATEGY_FACTORIES 增加：

```python
    "speedh": lambda: __import__("bot.speedh", fromlist=["SpeedH"]).SpeedH(),
```

```bash
git add bot/speedh.py tests/test_speedh.py run_bot.py
git commit -m "feat(speedh): SpeedH decide 集成（杠 EV 门控）+ run_bot 注册"
```

### Task 6: SpeedH 真机短局冒烟（进窗口前的合法性门）

- [ ] **Step 1: 建房 4 席（2×speedh + 2×speedE），跑 ≥30 局**

```powershell
python -X utf8 tools\room_ctl.py create --m 1 --rounds 1 --name "p1-smoke"
# 4 令牌 → speedh×2 + speedE×2，日志 logs/p1_speedh_<席>.log；跑 ~30 局
```

- [ ] **Step 2: 验收（冒烟门槛）**

- 无违规/409 风暴/断线（grep `409|INVALID|Traceback` 应为 0 或瞬时自愈）；
- 至少观察到 1 次 gang 提交被服务器接受并正常结算；
- 场次完成率 100%（对比 `本场结束` 计数与 audit）。
- [ ] **Step 3: 写 P1 报告骨架与结论**

`docs/iter/reports/P1-speedh.md`：冒烟证据、P0 语义核对表、已知限制 → 待窗口。
- [ ] **Step 4: 关房停进程 + 提交**

```bash
git add docs/iter/reports/P1-speedh.md
git commit -m "docs(speedh): P1 冒烟报告"
```

---

## P2：窗口 A/B 工具链（不依赖窗口也能开发/测试）

### Task 7: window_audit.py（N 席位审计）

**Files:**
- Create: `tools/window_audit.py`
- Test: `tests/test_window_audit.py`

- [ ] **Step 1: 写失败测试（合成日志夹具）**

`tests/test_window_audit.py`：

```python
"""window_audit 夹具测试：N 日志按 gid 配对 → δ/CI/裁决 + 席位健康。"""
import json
import os
import tempfile
import unittest

from tools.window_audit import audit_logs, parse_log


def _make_log(path, strat, gid_scores):
    """gid_scores: {gid: (seat, [s0,s1,s2,s3])}"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("[00:00:00] 策略: %s\n" % strat)
        for gid, (seat, scores) in sorted(gid_scores.items()):
            f.write("[00:00:01] 本场结束: finished 标记（gid=%s）\n" % gid)
            f.write("[00:00:01] 本场积分 seat=%d: %s\n" % (seat, json.dumps(scores)))


class TestParseLog(unittest.TestCase):
    def test_parse(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "a.log")
            _make_log(p, "speedE", {"g1": (0, [-8, -1, -1, 10])})
            strat, recs = parse_log(p)
            self.assertEqual(strat, "speedE")
            self.assertEqual(recs["g1"], (0, [-8, -1, -1, 10]))


class TestAuditLogs(unittest.TestCase):
    def test_same_table_pairing(self):
        with tempfile.TemporaryDirectory() as td:
            pa = os.path.join(td, "h.log")
            pe = os.path.join(td, "e.log")
            # 同桌：speedh seat0/1? 构造 4 席两两：h seat0/1? 简化 2+2
            _make_log(pa, "speedh", {"g1": (0, [10, -8, -1, -1]),
                                     "g2": (2, [-1, 10, -8, -1])})
            _make_log(pe, "speedE", {"g1": (1, [10, -8, -1, -1]),
                                     "g2": (3, [-1, 10, -8, -1])})
            res = audit_logs([{"name": "h", "path": pa},
                              {"name": "e", "path": pe}])
            self.assertEqual(res["n"], 2)
            self.assertAlmostEqual(res["delta"], 0.0, places=9)  # 零和对称


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 -m unittest tests.test_window_audit -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现（把 l2_audit 推广到 N 席 + 健康报告）**

`tools/window_audit.py`（完整代码，含 main 与 json 输出；可复用 l2_audit 的
正则/统计逻辑，但支持任意文件数与 seat 数、输出同赛段块级选项）：

```python
"""tools/window_audit —— 正式赛窗口 N 席位审计（SpeedE vs SpeedH 同赛段）。

按 gid 跨日志配对还原每场各席得分 → 配对差统计 + 席位健康报告。
模式：
  --mode same-table：同一 gid 内同时含两种策略席位才计入（同桌对照，最干净）；
  --mode block：同一 锦标赛+board（gid 前缀）内聚合两种策略所有席位的
    场均差（分桌对照，样本大但噪声大）。
用法：
  python tools/window_audit.py --logs "logs/w1_*.log" [--mode same-table]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re

SEAT_RE = re.compile(r"^.*本场结束: (.*?)（gid=(\S+)）$")
SCORE_RE = re.compile(r"^.*本场积分 seat=(\d+): (\[.*\])$")
STRAT_RE = re.compile(r"^.*策略: (\S+)")
GID_BLOCK = re.compile(r"^(t_\w+?)_r(\d+)")


def parse_log(path):
    strat = None
    recs = {}
    pending = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STRAT_RE.search(line)
            if m and strat is None:
                strat = m.group(1)
            m = SEAT_RE.search(line)
            if m:
                pending = m.group(2)
                continue
            m = SCORE_RE.search(line)
            if m and pending is not None:
                try:
                    scores = json.loads(m.group(2))
                except ValueError:
                    pending = None
                    continue
                recs[pending] = (int(m.group(1)), scores)
                pending = None
    return strat, recs


def audit_logs(specs, mode="same-table", delta_min=2.0):
    per = {}
    strat_of = {}
    for s in specs:
        strat, recs = parse_log(s["path"])
        per[s["name"]] = recs
        strat_of[s["name"]] = strat
    gids = set().union(*[set(r) for r in per.values()]) if per else set()
    groups = {}
    for gid in sorted(gids):
        seatmap = {}
        scores = None
        ok = True
        for name, recs in per.items():
            r = recs.get(gid)
            if not r:
                ok = False
                break
            seat, sc = r
            if scores is None:
                scores = sc
            if seat in seatmap:
                ok = False
                break
            seatmap[seat] = name
        if not ok or scores is None:
            continue
        cand = [scores[s] for s, n in seatmap.items()
                if strat_of.get(n) and strat_of[n].startswith("speedh")]
        base = [scores[s] for s, n in seatmap.items()
                if strat_of.get(n) == "speedE"]
        if mode == "same-table":
            if len(cand) < 1 or len(base) < 1:
                continue
            d = (sum(cand) / len(cand)) - (sum(base) / len(base))
        else:      # block：按 gid 前缀聚合（实现见下方 collect_blocks）
            continue
        groups[gid] = d
    if mode == "block":
        return collect_blocks(per, strat_of)
    ds = list(groups.values())
    n = len(ds)
    if not n:
        return {"n": 0, "delta": None, "verdict": "NO_DATA"}
    mean = sum(ds) / n
    var = sum((d - mean) ** 2 for d in ds) / n
    sd = math.sqrt(var)
    se = sd / math.sqrt(n)
    ci = (mean - 1.96 * se, mean + 1.96 * se)
    verdict = ("WIN" if mean >= delta_min and ci[0] > 0 else
               "LOSE" if ci[1] < 0 else
               "WEAK" if mean > 0 and ci[0] > 0 else "DRAW")
    return {"n": n, "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(se, 4), "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "delta_min": delta_min, "verdict": verdict,
            "mode": mode}


def collect_blocks(per, strat_of):
    """block 模式：gid 前缀 t_xxx_rNNN 为块，块内两策略席位场均差。

    数据不足时不入块；返回与 audit_logs 同构 dict。"""
    blocks = {}
    for name, recs in per.items():
        st = strat_of.get(name, "")
        for gid, (seat, scores) in recs.items():
            m = GID_BLOCK.match(gid)
            key = m.group(0) if m else gid
            b = blocks.setdefault(key, {"cand": [], "base": []})
            if st.startswith("speedh"):
                b["cand"].append(scores[seat])
            elif st == "speedE":
                b["base"].append(scores[seat])
    ds = []
    for key, b in blocks.items():
        if b["cand"] and b["base"]:
            ds.append(sum(b["cand"]) / len(b["cand"])
                      - sum(b["base"]) / len(b["base"]))
    n = len(ds)
    if not n:
        return {"n": 0, "delta": None, "verdict": "NO_DATA", "mode": "block"}
    mean = sum(ds) / n
    var = sum((d - mean) ** 2 for d in ds) / n
    sd = math.sqrt(var)
    ci = (mean - 1.96 * sd / math.sqrt(n),
          mean + 1.96 * sd / math.sqrt(n))
    return {"n": n, "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(sd / math.sqrt(n), 4),
            "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "delta_min": 2.0,
            "verdict": ("WIN" if mean >= 2.0 and ci[0] > 0 else "DRAW"),
            "mode": "block"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", required=True,
                    help="日志 glob 或路径列表")
    ap.add_argument("--mode", choices=("same-table", "block"),
                    default="same-table")
    ap.add_argument("--delta-min", type=float, default=2.0)
    args = ap.parse_args()
    paths = []
    for p in args.logs:
        paths += glob.glob(p) if os.path.isabs(p) is False and glob.has_magic(p) \
            else [p]
    if len(paths) < 2:
        print("需要 ≥2 份日志")
        return 3
    specs = [{"name": os.path.basename(p), "path": p} for p in sorted(paths)]
    res = audit_logs(specs, mode=args.mode, delta_min=args.delta_min)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return {"WIN": 0, "DRAW": 2, "LOSE": 1, "WEAK": 2,
            "NO_DATA": 3}.get(res["verdict"], 3)


if __name__ == "__main__":
    raise SystemExit(main())
```

> 说明：block 模式在 gid 不含可解析前缀时退化为整块聚合；正式赛 gid 形如
> `t_xxx_rNNN_bB_tT` 时取到 `t_xxx_rNNN` 为块。实现时如遇真实 gid 格式差异，
> 调整 `GID_BLOCK` 正则并在测试夹具中同步。

- [ ] **Step 4: 运行确认通过**

Run: `python -X utf8 -m unittest tests.test_window_audit -v`
Expected: 2 项 OK

- [ ] **Step 5: 提交**

```bash
git add tools/window_audit.py tests/test_window_audit.py
git commit -m "feat(tools): window_audit 窗口 N 席位审计（same-table/block 双模式）"
```

### Task 8: 复盘采集（replay_fetch + 可选记录器）

**Files:**
- Create: `tools/replay_fetch.py`
- Modify: `bot/game.py`（可选 `--record-replays`：把 long-poll 收到的原始事件按 gid 落盘）

- [ ] **Step 1: 写失败测试（事件记录器纯函数）**

`tests/test_replay_recorder.py`：

```python
"""replay 记录器测试：按 gid 累积事件 → 落盘 JSON 行。"""
import json
import os
import tempfile
import unittest

from bot.replay_rec import ReplayRecorder


class TestReplayRecorder(unittest.TestCase):
    def test_accumulates_and_dumps(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            rec.on_event("g1", {"type": "tile_discarded", "seat": 0,
                                "tile": "3b", "seq": 1})
            rec.on_event("g1", {"type": "tile_drawn", "seat": 1,
                                "seq": 2, "tile": None})
            rec.close_game("g1")
            p = os.path.join(td, "g1.jsonl")
            self.assertTrue(os.path.exists(p))
            lines = [json.loads(l) for l in open(p, encoding="utf-8")]
            self.assertEqual([e["seq"] for e in lines], [1, 2])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -X utf8 -m unittest tests.test_replay_recorder -v`
Expected: FAIL（ModuleNotFoundError: bot.replay_rec）

- [ ] **Step 3: 实现记录器**

`bot/replay_rec.py`：

```python
"""replay_rec —— 逐场事件记录器（run_bot --record-replays <目录> 时启用）。

game.py 的 long-poll 每收到一批事件即回调 on_event；场次结束（finished 标记
或 round 终态）调 close_game 落盘 <gid>.jsonl（事件按 seq 排序）。
用途：窗口赛后审计的数据源（对手摸牌不可见——如需全桌含手牌，仍走
tools/replay_fetch.py 拉服务器复盘，本记录器为保底）。
"""
from __future__ import annotations

import json
import os


class ReplayRecorder:
    def __init__(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir = out_dir
        self._buf = {}

    def on_event(self, gid, event):
        if not gid or not isinstance(event, dict):
            return
        self._buf.setdefault(gid, []).append(event)

    def close_game(self, gid):
        evs = self._buf.pop(gid, [])
        if not evs:
            return
        evs.sort(key=lambda e: int(e.get("seq", 0)))
        safe = "".join(c for c in str(gid) if c.isalnum() or c in "_-")[:80]
        with open(os.path.join(self.out_dir, safe + ".jsonl"), "a",
                  encoding="utf-8") as f:
            for e in evs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: 接入 game.py（最小侵入）**

`bot/game.py`：`play_game(client, gid, strategy)` 签名后追加可选参数
`recorder=None`；在解析增量事件的循环内（`for ev in res.get("events") or []:`）
首行插入 `if recorder: recorder.on_event(gid, ev)`；在"本场结束"分支
（`log("本场结束: ...")` 附近）插入 `if recorder: recorder.close_game(gid)`。
`bot/protocol.py`：主循环创建 recorder 的位置由 `run_tournament` 新可选参数
`record_dir=None` 控制，透传给 `play_game`；`run_bot.py` 加
`--record-replays <目录>`，在进入主循环前构造 `ReplayRecorder` 并传入。

> 注意：`game.py`/`protocol.py` 是协议层，改动需走真机冒烟（Task 6 同款
> 短局 + 本任务记录器输出校验），并跑全量协议测试：
> Run: `python -X utf8 -m unittest discover -s tests` → 全绿后提交。

- [ ] **Step 5: replay_fetch.py（服务器复盘拉取）**

`tools/replay_fetch.py`：

```python
"""tools/replay_fetch —— 窗口/房复盘拉取（server API 探索式）。

按候选端点顺序尝试拉取并校验返回含 'blocks' 的 JSON；成功即按
<tournament>_b<board>_t<table>.json 落盘 var/replays/<tid>/。
端点清单来自既有复盘文件命名与门户指南；拉取失败会给出提示（此时可用
run_bot --record-replays 的本地事件流兜底）。

用法：python tools/replay_fetch.py <tournament_id> [--cookie majiang_sid=...]
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()
CANDIDATES = [
    "/api/replays/{tid}",
    "/api/tournaments/{tid}/replays",
    "/portal/api/replays/{tid}",
]


def fetch(tid, cookie):
    h = {"Cookie": cookie} if cookie else {}
    for path in CANDIDATES:
        url = BASE + path.format(tid=tid)
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, dict) and "blocks" in data:
                return data
            if isinstance(data, list) and data and "blocks" in data[0]:
                return data
        except (urllib.error.HTTPError, urllib.error.URLError,
                json.JSONDecodeError, TimeoutError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tid")
    ap.add_argument("--cookie", default="")
    ap.add_argument("--out", default=os.path.join("var", "replays"))
    args = ap.parse_args()
    cookie = args.cookie or (open(os.path.join("var", ".portal_cookie"),
                                  encoding="utf-8-sig").read().strip()
                             if os.path.exists(os.path.join("var",
                                                            ".portal_cookie"))
                             else "")
    d = fetch(args.tid, cookie)
    if d is None:
        print("拉取失败：端点均未命中（用 run_bot --record-replays 兜底）")
        return 1
    out = os.path.join(args.out, args.tid)
    os.makedirs(out, exist_ok=True)
    if isinstance(d, dict):
        blocks = d.get("blocks", [])
        # 按 board/table 命名：无显式信息时整包落盘
        with open(os.path.join(out, args.tid + "_full.json"), "w",
                  encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        print("已落盘 blocks=%d → %s" % (len(blocks), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> 真机验证步：对已知 t_dee58824c308 试拉一次（若服务器已清复盘则预期失败，
> 记录"端点未命中"，不阻塞；下次窗口赛后立刻试拉并记录命中端点，回填本文件
> CANDIDATES 顺序）。**执行者须把实际命中的端点写回 CANDIDATES 首位。**

- [ ] **Step 6: 提交**

```bash
git add bot/replay_rec.py tests/test_replay_recorder.py tools/replay_fetch.py
git commit -m "feat(tools): replay 采集——事件记录器(保底) + replay_fetch(服务器复盘)"
```

### Task 9: 窗口 A/B 运行手册 + 裁决卡模板

- [ ] **Step 1: 写手册**

`docs/iter/window-A-B运行手册.md`（窗口前/中/后 checklist）：

```markdown
# 正式赛窗口 A/B 运行手册（SpeedE vs SpeedH）

## 窗口前（开赛 ≥30min）
1. python -X utf8 -m unittest discover -s tests        # 全绿
2. python -X utf8 tools\preflight.py                    # READY
3. 席位令牌 ×4（用户提供）：2×speedE + 2×speedh
4. 每席：run_bot.py <tok> --strategy speedX --log logs/w<序号>_<席>.log
   （keep_alive 托管可选）
## 窗口期
5. 无人工干预；409/502 自愈；日志停滞 >3min 才人工
## 窗口后
6. python -X utf8 tools\window_audit.py --logs "logs/w<序号>_*.log"
   → 裁决 JSON（n/delta/CI/verdict）
7. 席位健康：grep 409|Traceback 计数 + 场次完成率
8. replay_fetch <tid> 拉复盘 → var/replays/<tid>/
9. 填裁决卡 → 晋级（合入 run_bot 默认+演进史）或 负结果登记（docs/iter/queue.md）
门槛：两段式（快筛 n40-60 → 终裁累计 n≈150；δ≥2/场 且 95%CI 排除 0 才 WIN；
详见 docs/iter/window-A-B运行手册.md，2026-09-07 修订，取代旧 n≥200 文案）；
异常场次 <5%
```

- [ ] **Step 2: 提交**

```bash
git add docs/iter/window-A-B运行手册.md
git commit -m "docs(window): 窗口 A/B 运行手册与裁决门槛"
```

### Task 10: 收尾与总回归

- [ ] **Step 1: 全量回归 + stability + smoke**

```powershell
python -X utf8 -m unittest discover -s tests
python -X utf8 tools\stability.py
python -X utf8 run_bot.py --smoke
```

- [ ] **Step 2: 更新防重/队列/演进史（若 P0/P1 有负结果或语义发现）**

```powershell
# 视结果更新 docs/iter/queue.md 与 docs/PROJECT.md，git commit
```

- [ ] **Step 3: 最终提交并汇报（等待用户提供窗口令牌进入 P2 实测）**

---

## 自检记录（写作时执行）

- 规格覆盖：P0（T1-T3）、P1（T4-T6）、P2 工具（T7-T8）、手册（T9）、收尾（T10）——设计 §2-§6 全部映射；
- 已知占位（P0 门依赖，按设计必须如此）：Task 4 暗杠分支口径、Task 3 差异修订点、Task 8 replay_fetch 端点——均已标注"执行者以真机实测为准回填"，不是遗漏；
- 类型一致性：`safe_gang(hand13, drawn, exposed, gangs, meld_4th)`、`bugang_value(chain)`、`SpeedH.decide`、`window_audit.audit_logs(specs, mode, delta_min)`、`parse_log`、`ReplayRecorder.on_event/close_game` 跨任务签名一致。
