# -*- coding: utf-8 -*-
"""SpeedTM —— SpeedT(tie 弃牌偏好) + SpeedM(副露放宽) 组合候选。

C012 弃牌画像（拆对后置/孤张优先）与 C010 副露放宽（after<=before 即接受）
为两个独立机制（弃牌路径 vs 窗口成型），组合以逼近冠军听牌率（50-72%）。
弃牌 = _best_discard_t（SpeedT）；窗口 = want_claim_mild（SpeedM 判据）；
其余继承 SpeedE。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn, window_pending
from .speedm import want_claim_mild
from .speedt import _best_discard_t
from .speede import SpeedE


class SpeedTM(SpeedE):
    def __init__(self, name="speedTM"):
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
                    tile = _best_discard_t(hand, drawn, exposed, gangs)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
