# -*- coding: utf-8 -*-
"""C2xx —— 弃胡换爆头的 **EV 修正版**：p_conv 随河长衰减 + 补上失败负项。

## 为什么改（2026-09-23 实测，69 次真实弃胡逐条验算）

`SpeedTUG._best_giveup` 的原始判据是 `p_conv × fan_baotou > fan_now`，
其中 **`p_conv = 0.71` 是与巡数无关的常数**，且**失败那一支被当成 0**。
用 80 个决策日志文件（`*.dec.jsonl`）验算全部「可胡却弃胡」并追踪结局：

| 河中牌数（≈巡数） | 弃胡次数 | 我们胡回 | 真实转化率 |
|---|---:|---:|---:|
| <20（前盘）   | 20 | 19 | **95.0%** |
| 20–39（中盘） | 41 | 37 | **90.2%** |
| 40–54（后盘） |  6 |  4 | **66.7%** |
| ≥55（末盘）   |  2 |  2 | （n=2，无统计意义）|
| 合计          | 69 | 62 | 89.9% |

⇒ 两个方向都与常数 0.71 不符：**前盘被低估**（少弃了本该弃的）、**后盘被高估**
（弃出了本该胡的）——正是「最后几巡还不胡」的来源。

## 失败负项的推导（口径来自服务端 fan-calc 实测）

服务端分值（`scores` 字段实测）：
- 闲家自摸胡：`win = 10 × fan`（庄付 8×fan，另两家各付 1×fan）
- 庄家自摸胡：`win = 24 × fan`（三家各付 8×fan）

弃胡失败 = 别家自摸胡走 ⇒ 我方**赔付**：
- 我是闲家：输家是庄（概率≈1/3）付 8×fan_opp；输家是闲（≈2/3）付 1×fan_opp
  ⇒ `E[赔付] ≈ 3.33 × fan_opp`
- 我是庄家：任何一家胡我付 8×fan_opp ⇒ `E[赔付] = 8 × fan_opp`

折算进「我方胡法的番当量」（除以我方单位 10 或 24）后**两式都 ≈ fan_opp / 3**
⇒ 取对手典型 `fan_opp ≈ 1.5` ⇒ **`loss_fan ≈ 0.5` 番当量**（类属性，可调、待 A/B 校准）。

## 判据（本臂）

```
give up  iff   p(river) × fan_baotou − (1 − p(river)) × loss_fan  >  fan_now
```

`p(river)` 用上表实测值分段；**末盘（≥55）无数据，取先验 0.40**（牌山将尽，
且该段样本 n=2 不足以定值）——**这一段是本臂唯一的先验假设，须由 A/B 校准**。

## 单变量切分（预登记用）

- `SpeedGiveupRiverP`（`speedgiveupriverp`）：**只**换 p(river)，`loss_fan=0`
  ⇒ 与 `speedvalue`/`speedc151` 比，隔离「p 随巡数」这一轴；
- `SpeedGiveupRiver`（`speedgiveupriver`）：p(river) **+** loss_fan
  ⇒ 与 `SpeedGiveupRiverP` 比，隔离「失败负项」这一轴。

## ★ 诚实的局限（2026-09-23 上线前实测，必须写清，勿当"已验证的修法"）

1. **末盘那一段是「先验」，不是实测**：`>=55` 观测到的弃胡只有 **2 次**，
   而且**两次都胡回来了**（转化率 2/2）⇒ 本臂在该段一律改判"胡"，
   在这两个样本上其实是**更差**的选择。`p=0.40` 纯属牌山将尽的物理先验，
   **证据方向甚至相反**，必须由 A/B 校准（这才是本臂要回答的问题）。
2. **影响面很小**：判据只在阈值附近才翻转，而真实决策大多离阈值很远。
   用 800 个真机 draw 局面跑 `tools/arm_smoke.py --kind draw`：
   **本臂与现役 `speedvalue` 的动作分布逐项相同**（discard/hu/gang 计数全等）
   ⇒ 常见局面下它是 **no-op**，只有末盘那类罕见组合才翻转。
   （对 69 次真实弃胡：`river<20` 20 次、`20-39` 41 次、`40-54` 6 次、`>=55` **2 次**。）
3. 因此本臂的定位是「**边际修正 + 可被证伪的假设**」，
   **不是"能把总分翻正的轴"**（这一点须与「杠缺口 2.7x」「第一率 18%→25%」区分开）。


其余 100% 继承 `SpeedValue`（出牌/副露/杠/财飘/胡牌判定均未动）。
"""
from __future__ import annotations

from mahjong.hu import is_baotou

from .speedvalue import SpeedValue


class SpeedGiveupRiverP(SpeedValue):
    """只改 p_conv：随河长分段衰减；loss_fan = 0（保持与旧式判据同构）。"""

    NAME = "speedgiveupriverp"
    # (上界, p) —— 由实测转化率给出；最后一段为先验
    P_SEGMENTS = ((20, 0.95), (40, 0.90), (55, 0.67), (10 ** 9, 0.40))
    LOSS_FAN = 0.0

    def __init__(self, name=None, loss_fan=None):
        super().__init__(name or self.NAME)
        self.loss_fan = float(self.LOSS_FAN if loss_fan is None else loss_fan)
        self._river_len = 0

    @classmethod
    def p_conv_at(cls, river_len):
        """按河中牌数取转化率（分段，实测值 + 末盘先验）。"""
        try:
            r = int(river_len)
        except (TypeError, ValueError):
            r = 0
        for hi, p in cls.P_SEGMENTS:
            if r < hi:
                return p
        return cls.P_SEGMENTS[-1][1]

    def decide(self, view):
        # river_len 由 game.py 注入（view["river_len"]）；缺字段时用河长兜底
        try:
            self._river_len = int(view.get("river_len") or len(view.get("river") or []))
        except (TypeError, ValueError):
            self._river_len = 0
        return super().decide(view)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        """与 SpeedTUG 同构，但判据换成 p(river)×fan_baotou − (1−p)×loss_fan > fan_now。"""
        best, best_fan = None, None
        for d in sorted(set(hand)):
            after = list(hand)
            after.remove(d)
            try:
                if not is_baotou(after, allow_qidui=(exposed == 0 and gangs == 0),
                                 exposed_melds=exposed, gangs=gangs):
                    continue
            except ValueError:
                continue
            fb = self._baotou_fan(after, exposed, gangs, chain)
            if fb is None:
                continue
            if best_fan is None or fb > best_fan:
                best, best_fan = d, fb
        if best is None:
            return None
        p = self.p_conv_at(self._river_len)
        ev = p * float(best_fan) - (1.0 - p) * self.loss_fan
        return best if ev > float(fan_now) else None


class SpeedGiveupRiver(SpeedGiveupRiverP):
    """在 P 版之上再加「失败负项」（loss_fan = 0.5 番当量）。"""

    NAME = "speedgiveupriver"
    LOSS_FAN = 0.5
