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
                        if t != "白" and hand.count(t) >= 1:
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
                tile = drawn if hand.count(drawn) >= 1 else hand[0]
                return {"action": "discard", "tile": tile}
        return super().decide(view)
