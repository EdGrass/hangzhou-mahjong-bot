# -*- coding: utf-8 -*-
"""SpeedP —— SpeedE + 打点/弃胡分支 v0（爆头摸白 → 财飘链取舍，2026-09-08）。

SpeedP 与 SpeedE 的唯一差异 = draw 回合【可胡且爆头态摸白】时，选择弃胡打
白飘（财飘）而非立即胡：

规则依据（接入指南 §1.2，2026-09-08 fan-calc/引擎黄金集全对齐）：
- 弃胡合法（P0 实测；可胡超时才被服务端自动胡兜底——我们显式提交 discard）；
- 爆头态摸到白板：可提交 hu（爆头 ×2），也可弃胡打白飘——每飘 1 动作链 ×2
  （财飘 = 爆头×飘1 = ×4 起，双财飘 ×8…三财飘 ×16）；
- 手留白 + 链内飘出白 == 4 → 4白板 ×2（与链叠加）；
- 弃白触发抓打圈：此后一圈别家禁吃/碰/明杠、出牌只能打刚摸——对手进程受抑，
  飘的代价主要是别家先自摸/末盘流局；
- 关键恒等式：爆头态摸白 → 弃【刚摸的白】= 手牌精确回到摸前 13 张（爆头态），
  下一次自摸必胡（fan 已 ×2）→ 每次飘只赌"一个对手回合圈内无人先胡/不流局"。

决策（v0 保守门控，参数可配，超参默认值待 oracle/真机校准）：
  当 is_win(drawn) 且 god.baotou 且 drawn==白：
    - god.chain_count < max_chain（默认 3）：链已达上限 → hu；
    - 河长 < late_river（默认 55，公开弃牌河近似末盘度）：末盘流局风险 → hu；
    - 满足 → discard 刚摸的白（财飘）；否则 hu。
  其余 100% 继承 SpeedE（窗口/副露/孤字 tie/抓打圈强制语义不变）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn
from .speede import SpeedE

GOD_TILE = "白"


class SpeedP(SpeedE):
    def __init__(self, name="speedP", max_chain=3, late_river=55):
        super().__init__(name)
        self.max_chain = int(max_chain)
        self.late_river = int(late_river)

    def _want_piao(self, drawn, chain, river_len):
        """财飘门控（纯函数可测）：必须爆头态摸白；链上限 + 末盘流局保护。"""
        if drawn != GOD_TILE:
            return False
        if chain >= self.max_chain:
            return False
        if river_len >= self.late_river:
            return False
        return True

    def decide(self, view):
        if my_turn(view):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu and drawn:
                god = view.get("god") or {}
                chain = int(god.get("chain_count") or 0)
                if god.get("baotou") and self._want_piao(
                        drawn, chain, len(view.get("river") or [])):
                    # 弃刚摸的白 → 精确回到摸前爆头 13 张，链 ×2（服务端记账）
                    return {"action": "discard", "tile": drawn}
                return {"action": "hu", "tile": ""}
        # 非胡局面 / 窗口 / 抓打圈强制：行为与 SpeedE 完全一致
        return super().decide(view)
