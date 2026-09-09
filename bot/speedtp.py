# -*- coding: utf-8 -*-
"""SpeedTQ —— SpeedTM + 碰判据恢复严格（C017，2026-09-09）。

动机（阿飞画像）：阿飞 = 纯平胡速度流（0 爆头、fan 1.03）听牌率 66.2%/
胡率 36.2%，副露吃 52 > 碰 34（顺子快攻）；我们 TM/TQM 真机房碰 ≥ 吃
（如 chi34 peng57）——碰刻消费对子/将、减少暗牌与白保留机会，可能拖慢
成型（真机有对手截断，慢 = 死）。C017 = 吃保持 mild（after<=before），
碰/明杠恢复严格（after<before，同 SpeedE 原判据）。
sim（8 seeds）：听牌 67.6%（≈TM 68.0%）、番 1.05（>TM 1.02）——真机验证。
"""
from __future__ import annotations

from .speedtm import SpeedTM
from .speedm import want_claim_mild


class SpeedTP(SpeedTM):
    """TM + 碰严格化（吃 mild / 碰严格）。"""

    def __init__(self, name="speedTP"):
        super().__init__(name)

    def decide(self, view):
        from .model import window_pending
        if window_pending(view) and view.get("offer_tile"):
            cnt = view["my_hand"].count(view["offer_tile"])
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_mild(view, "gang_ming",
                                                allow_equal=False):
                    return {"action": "gang", "tile": view["offer_tile"]}
                if cnt >= 2 and want_claim_mild(view, "peng",
                                                allow_equal=False):
                    return {"action": "peng", "tile": view["offer_tile"]}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi" and \
                    want_claim_mild(view, "chi"):
                return {"action": "chi", "tile": view["offer_tile"]}
            return {"action": "pass", "tile": ""}
        return SpeedTM.decide(self, view)
