"""SpeedE —— SpeedD 序号的下一变体：同向听 tie 内「孤张字牌优先」弃牌。

复盘证据（正式赛同桌 TOP3/7/10，227 手逐手审计）：
顶尖玩家的同向听分歧 90%+ 为「先弃孤张字牌（进张仅 3），后弃花色浮张
（进张 6-11）」——即用弃牌顺序近似 ukeire 最大化；我们 tie 仅保留刚摸。
本变体把 tie 键改为：孤张字牌优先 → 非字（花色浮张）→ 保留刚摸。

其余决策继承 SpeedB（副露收益判据）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import window_pending
from .speed import W, _melds_info
from .speedb import SpeedB, _claim_value, _chi_pairs, _want_claim  # noqa: F401

HONOR = set("东南西北中发白")


def _best_discard_honor(hand, drawn, exposed, gangs):
    """弃牌：向听最小 → 听牌等待最大 → 孤张字牌优先 → 保留刚摸。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs)) if s == 0 \
            else 0
        is_honor = d in HONOR          # 孤张字牌（对子以上仍会先被向听抓住）
        key = (s, -wcnt, 0 if is_honor else 1, -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedE(SpeedB):
    def __init__(self, name="speedE"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view):
            return super().decide(view)
        from .model import my_turn
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
                return {"action": "discard",
                        "tile": _best_discard_honor(hand, drawn, exposed, gangs)}
            return None
        return super().decide(view)
