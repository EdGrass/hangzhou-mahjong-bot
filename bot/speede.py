"""SpeedE —— 当前唯一竞技策略（基准）。

决策（顺序自检）：
1) 可胡即胡（含爆头摸白——纯速度不做财飘/打点绕路）；
2) 出牌：主键 = 弃后【精确向听数】（含财神/副露；越小越好），
   次键 = 若听牌【等待牌数】越多越好，再次 = 【孤张字牌优先】（复盘驱动：
   正式赛 TOP3/7/10 逐手审计显示同向听 tie 里他们先弃孤字——近似 ukeire），
   末键 = 保留刚摸；抓打圈强制打刚摸牌；
3) 窗口：碰/直杠/吃仅当副露后成型更快（after < before）才响应（已听不碰）；
4) 自杠（暗杠/补杠）：不做。

历史：SpeedA（纯向听+无条件副露）→ SpeedB（副露收益判定）→ SpeedE
（+孤字优先 tie）为演进链；SpeedF（ukeire 精确化）经真机同桌 400+ 局
验证与 E 统计不可分，已并入主线评估而非保留分支。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import (HONOR, SpeedCore, _best_discard, _claim_value,  # noqa: F401
                    _chi_pairs, _melds_info, _min_shanten_after_discard,
                    _want_claim)


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


class SpeedE(SpeedCore):
    def __init__(self, name="speedE"):
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
                    tile = _best_discard_honor(hand, drawn, exposed, gangs)
                except ValueError:
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        # 窗口与非窗口逻辑继承 SpeedCore/SpeedBase
        return super().decide(view)
