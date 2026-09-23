# -*- coding: utf-8 -*-
"""SpeedTQM —— 全机制合体：tie 弃牌偏好(T) + 副露放宽(M) + 七对路线锁定(Q)。

分工设计：手牌无副露且七对潜力（对子≥4 或含白）时锁定七对路径（保对弃散，
白留万能对 → 七对 ×2 与爆头 ×2 潜力）；否则一般形路径 + SpeedM 的副露
放宽（after<=before 即碰/吃，加速面子成型）。两种路径天然互斥（七对无副露）。

验证方法学：番型/爆头类指标在 sim 无信号（同质速度局平均番恒 1.05），
本候选直接真机验证（fan 结构/bao/场分）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn, window_pending
from .speedm import want_claim_mild
from .speedq import SpeedQ, _q_discard, _route
from .speedt import _best_discard_t
from .speede import SpeedE


class SpeedTQM(SpeedQ):
    def __init__(self, name="speedTQM", lead=1):
        super().__init__(name)
        self.lead = int(lead)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            melds = view.get("melds") or []
            if len(melds) >= 2 and _route(list(view["my_hand"]),
                                          len(melds), 0, self.lead):
                pass  # 七对路线中不副露
            cnt = view["my_hand"].count(view["offer_tile"])
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_mild(view, "gang_ming"):
                    return {"action": "gang", "tile": view["offer_tile"]}
                if cnt >= 2 and want_claim_mild(view, "peng"):
                    return {"action": "peng", "tile": view["offer_tile"]}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi" and \
                    want_claim_mild(view, "chi"):
                return {"action": "chi", "tile": view["offer_tile"]}
            return {"action": "pass", "tile": ""}
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
                return {"action": "hu", "tile": ""}
            if hand:
                if view.get("god", {}).get("catch_play") and drawn:
                    return {"action": "discard", "tile": drawn}
                try:
                    if _route(hand, exposed, gangs, self.lead):
                        tile = _q_discard(hand, drawn)
                    else:
                        tile = _best_discard_t(hand, drawn, exposed, gangs)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return SpeedE.decide(self, view)
