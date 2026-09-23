# -*- coding: utf-8 -*-
"""SpeedC155 —— **庄位条件化的路线项**（`speedc151` 的单变量）。

唯一差别：多对子惩罚（c151 的路线加成）**只在做庄时生效**；做闲时退回 `speedc150`（无路线项）。

动机（2026-09-16，已修正的门户口径）：
- 价值分解里**庄胡收入 = 67% 的缺口**（§9.16），庄胡率我们 26.3% vs 强手 32.1%、庄占比 24.7% vs 28~33%；
  §9.29 用**分解**（不是实验）判"不存在庄位专用打法"，据此关掉了这个方向 —— 但我们的策略是**启发式**、
  不是赔付 EV 最优，所以"按座位区分"这件事**从未被真机测过**；
- 赔付结构：赢的价值对庄/闲**均匀放大**（24m : 10m = 2.4），但**下行不均匀**（做庄时对手自摸我们要付 8m，
  做闲时多数情况只付 1m）⇒ 做庄时**偏向"把听牌速度换出来、早点锁定一胡 + 连庄"**；
  做闲时下行小、且单胡价值低（10m）⇒ 更值得**保对子/七对/爆头那一路的价值**；
- 而 c151 的路线项是"**全局生效**的多对子惩罚"（拿价值换速度）⇒ 本臂把它**限定在做庄**。

预期（**先写下来**）：庄胡率 ↑（主端点）、做闲时的番/爆头占胡 ↑、非庄位的弃牌与 c150 逐位一致；
判据仍是 `tools/ab_readout.py` 的净胜/房（150 房/臂、t≥1.5 才采用），机制层用
`tools/ab_portal_readout.py`（胡率/爆头占胡/番）+ `var/_own_fan_audit.py`（零延迟价值端点）。
"""
from __future__ import annotations

from .speedc150 import SpeedC150
from .speedc151 import SpeedC151


class SpeedC155(SpeedC151):

    def __init__(self, name="speedc155"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        """做庄 ⇒ c151（多对子惩罚，换速度）；做闲/庄家未知 ⇒ c150（不惩罚，保对子价值）。"""
        try:
            dealer = (view or {}).get("dealer")
            seat = (view or {}).get("seat")
            is_dealer = bool(isinstance(dealer, int) and dealer == seat)
        except Exception:
            is_dealer = False
        if is_dealer:
            return SpeedC151._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        return SpeedC150._pick_discard(self, hand, drawn, exposed, gangs, view=view)
