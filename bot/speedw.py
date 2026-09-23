# -*- coding: utf-8 -*-
"""SpeedW —— SpeedT + 白保留评估模式（C013，2026-09-09）。

动机（复盘铁证）：E 族 1360 局爆头态到达率 0.0% vs 冠军 8-16%（陶康 15%、
国士无双 16.2%）；冠军爆头局 80% 起手有白——白留作最终万能单骑（4面子+白 /
6对+白 → 任意摸即胡 ×2）。E 的向听最小把白当"万能补张"随时消费进面子 →
从未形成爆头态，每胡平胡 1 番（fan 1.10 vs 冠军 1.3-1.72）。

SpeedW 与 SpeedT 唯一差异：弃牌向听评估用 god_meld=False（白不得补面子，
仅可做对子/塔伴侣/孤张）→ 白自然地保留到成型末位；副露/窗口 = SpeedE 原判据
（可后续叠加 SpeedM 的放宽）。

风险与回退：白受限使向听评估保守化——若 sim 显示听牌率/胡率显著受损
（白浪费过多），回退至 SpeedT 或做"部分保留"中间档（见 docs 报告）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn
from .speedt import SpeedT, _best_discard_t


class SpeedW(SpeedT):
    """E + tie 弃牌偏好 + 白保留（白不补面子）评估。"""

    def __init__(self, name="speedW"):
        super().__init__(name)

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
        return super().decide(view)
