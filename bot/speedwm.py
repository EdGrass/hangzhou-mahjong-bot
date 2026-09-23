# -*- coding: utf-8 -*-
"""SpeedWM —— SpeedW(白保留评估) + SpeedM(副露放宽) 组合（C013 v2）。

爆头主流路径（204 例实测）：副露 2-3 组 + 暗牌"面子齐+白孤"（任意摸：
白+X 成将 → 4 面子+将胡，fan×2）；零副露次级 = 六对半+白（七对爆头）。
W 提供白孤保留，M 提供副露推进 → 组合应触发爆头态。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn, window_pending
from .speedm import want_claim_mild
from .speedw import SpeedW
from .speedt import _best_discard_t


class SpeedWM(SpeedW):
    def __init__(self, name="speedWM"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
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
                    tile = _best_discard_t(hand, drawn, exposed, gangs,
                                           god_meld=False)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return SpeedW.decide(self, view)
