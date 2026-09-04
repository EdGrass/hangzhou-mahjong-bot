"""SpeedC —— SpeedB 增强变体（V2：自杠收益判定）。

在 SpeedB（副露收益判定）基础上增加摸牌回合的 自杠（暗杠/补杠）收益判定：
仅当 杠后（去 3/4 张 + 面子数增加 + 最优弃 1 张）的精确向听 < 不杠最优出牌的
向听时才执行（暗杠=手牌 4 张同码；补杠=碰组 + 第 4 张）。

其余决策继承 SpeedB。
"""
from __future__ import annotations

from .model import my_turn
from .speed import _best_discard, _melds_info
from .speedb import SpeedB, _min_shanten_after_discard
from mahjong.hu import is_win
from mahjong.shanten_exact import shanten as exact_shanten

W = "白"


def _self_gang_benefit(hand, exposed, gangs, melds):
    """自杠收益：返回 (是否值得杠, tile)。杠后向听 < 不杠最优出牌向听才杠。"""
    # 不杠基线：摸牌态（14-3e-g）最优弃 1 张后的向听
    base = _min_shanten_after_discard(hand, exposed, gangs)
    # 暗杠：4 张同码（白板禁杠）
    for t in sorted(set(hand)):
        if t == W or hand.count(t) != 4:
            continue
        h = list(hand)
        for _ in range(4):
            h.remove(t)
        # 暗杠后须出 1 张（sim 语义：杠不补牌）
        after = _min_shanten_after_discard(h, exposed + 1, gangs + 1)
        if after < base:
            return True, t
    # 补杠：碰组 tile 且手牌有第 4 张
    peng_tiles = [m.get("tile") for m in (melds or [])
                  if m.get("type") == "peng"]
    for t in peng_tiles:
        if t != W and t in hand:
            h = list(hand)
            h.remove(t)
            after = _min_shanten_after_discard(h, exposed, gangs + 1)
            if after < base:
                return True, t
    return False, None


class SpeedC(SpeedB):
    def __init__(self, name="speedC"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view) and view.get("drawn_tile"):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed, gangs = _melds_info(view)
            # 可胡优先（继承语义）：先判断胡，再判断自杠
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:
                hu = False
            if hu:
                return {"action": "hu", "tile": ""}
            if view.get("can_gang", False):
                worth, tile = _self_gang_benefit(hand, exposed, gangs, melds)
                if worth:
                    return {"action": "gang", "tile": tile}
        return super().decide(view)
