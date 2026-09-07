"""speedprobe —— 真机规则语义探针策略（仅测试房用，勿参赛）。

ProbeGang：my_turn（有 drawn_tile）时：
  1) 先判胡——可胡则直接交还 SpeedE（胡优先，避免胡形提交 gang 被 409 卡死窗口）；
  2) 否则有碰组且手牌含该碰牌第 4 张（白板除外）→ 提交补杠 gang；
  3) 或手牌含 4 张同码（白板除外）→ 提交暗杠 gang；
  均不中才回退 SpeedE 决策。
  （can_gang 键仅 sim/离线测试注入，真机视图从不产出；探针不再预判可杠性，
   一律让服务器裁决——409 同样是观测信号。）
ProbeHuPass：可胡（含刚摸）时改提交 discard —— 探测服务器是否允许"过胡"。
设计动机：sim v2 杠后不补牌且与规则文档矛盾；本 bot 从未在 draw 回合提交过
gang——服务器对 暗杠/补杠/过胡 的真实响应（事件序列/409/倍率）只能真机观察。
"""
from __future__ import annotations

from mahjong.hu import is_win

from .model import my_turn
from .speede import SpeedE


class ProbeGang(SpeedE):
    """my_turn 时强制触发 gang 场景（胡形交还 SpeedE，均不中回退 SpeedE）。"""

    def __init__(self, name="probe_gang"):
        super().__init__(name)

    def decide(self, view):
        phase = view.get("phase") or ""
        # 窗口覆盖：响应他人弃牌（碰/吃窗口），无条件造碰/杠机会以加速补杠/直杠观测。
        # 白板弃出无人可吃碰杠（sim.py L10/173）→ offer 为白一律 pass。
        offer = view.get("offer_tile")
        if phase == "response_peng" and offer and view.get("seat", -1) in (
                view.get("responding_seats") or []):
            if offer == "白":
                return {"action": "pass", "tile": ""}
            cnt = view["my_hand"].count(offer)
            if cnt >= 3:
                return {"action": "gang", "tile": offer}   # 直杠也观测
            if cnt >= 2:
                return {"action": "peng", "tile": offer}   # 无条件碰：制造补杠机会
            return {"action": "pass", "tile": ""}
        # 原 my_turn 杠逻辑：可在 my_turn（有 drawn_tile）提交暗杠/补杠
        if my_turn(view) and view.get("drawn_tile"):
            hand = view["my_hand"]
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            # hu 优先守卫：可胡形直接交还 SpeedE(→hu)，避免提交 gang 遭服务器 409 卡死窗口。
            # 不再读 can_gang（真机视图无该键）：探针不预判可杠性，提交与否交给服务器裁决。
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu:
                return super().decide(view)
            # 补杠：有碰组且手牌含该碰牌第 4 张（白板除外）
            for m in melds:
                if m["type"] == "peng":
                    t = m["tile"]
                    if t != "白" and hand.count(t) >= 1:
                        return {"action": "gang", "tile": t}
            # 暗杠：4 张同码（白板除外）
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
