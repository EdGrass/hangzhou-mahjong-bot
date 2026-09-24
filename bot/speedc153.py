# -*- coding: utf-8 -*-
"""SpeedC153 —— **强制爆头（`YouCaiBiKao=true` 保险臂 v2）**。

背景（STATUS §9.36 实测）：若正式赛 config 为 `YouCaiBiKao=true`，我方**历史胡牌里 64.4%**
是"手上有白 ∧ 平胡" ⇒ 在该规则下**全部非法**。而 `speedc148` 只是**闸门**：
被挡之后它直接调 `_pick_discard` 弃牌，**没有走 C036 的 `_best_giveup`** ⇒
"挡掉之后朝爆头继续打"这一块是缺的。

**本臂 = `speedc148` 的唯一差别**：被闸门挡掉时，**先找"能把 13 张变成爆头形"的弃牌**；
找不到才退回 `_pick_discard`。
- 判据上用 `fan_now = 0`：**此刻我们本来就胡不了**，所以"能不能变爆头"与"现在几番"无关，
  任何能形成爆头形的弃牌都值得走（C036 的 EV 门槛在"不能胡"的场景下不适用）；
- 其余（`GOD_MELD=False`、合法性闸门、C146 全机制、C036 可选弃胡）**全部继承**。

⚠ **无法在阶梯上 A/B**（阶梯是 `YouCaiBiKao=false`，闸门会错误拦掉合法平胡）
⇒ 验证路径 = 单测 + `offline_replay` 窗口级 footprint；**触发条件：正式赛 `/rules` 读到 `YouCaiBiKao=true`**。
"""
from __future__ import annotations

from .speedc146 import SpeedC146
from .speedc148 import SpeedC148


class SpeedC153(SpeedC148):
    def __init__(self, name="speedc153"):
        super().__init__(name)

    def decide(self, view):
        # ⚠ 这里显式从 **SpeedC146** 起算：c148.decide 会在违规时直接 `_pick_discard`，
        #   那样就绕过了本臂要加的"朝爆头弃牌"这一步。
        act = SpeedC146.decide(self, view)
        if not (isinstance(act, dict) and act.get("action") == "hu" and self.YOU_CAI_BI_KAO):
            return act                      # 上游（含 C036）已给出弃牌，或本来就没胡

        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds
                    if isinstance(m, dict) and m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        pre = list(hand)
        if drawn and drawn in pre:
            pre.remove(drawn)

        if not self._ycbk_violation(view, pre, exposed, gangs):
            return act                      # 合法胡 ⇒ 照常胡

        # ★ 本臂唯一差别：先找"能变成爆头形"的弃牌（此刻胡不了 ⇒ 不用 EV 门槛，传 fan_now=0）
        tile = None
        try:
            god = view.get("god") or {}
            chain = {"count": int(god.get("chain_count") or 0),
                     "piao": int(god.get("piao_count") or 0)}
            tile = self._best_giveup(list(hand), exposed, gangs, 0, chain)
        except Exception:
            tile = None
        if tile is None:
            try:
                tile = self._pick_discard(hand, drawn, exposed, gangs, view=view)
            except Exception:
                tile = hand[0] if hand else ""
        return {"action": "discard", "tile": tile}
