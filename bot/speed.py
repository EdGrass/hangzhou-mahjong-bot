"""启发式策略 SpeedA —— 纯速度基准（S2：向听数驱动的最强传统算法）。

决策（顺序自检）：
1) 可胡即胡（含爆头摸白——纯速度不做财飘/打点绕路，飘留待模型权衡学习）；
2) 出牌：主键 = 弃后【精确向听数】（含财神/副露；越小越好），
   次键 = 若听牌【等待牌数】越多越好（ukeire），再次 = 抓打圈强制刚摸牌；
   同分偏好保留刚摸的牌；
3) 窗口：可直杠/碰就要（加快/成型判断留给 Arena 数据说话）；吃全过；
4) 自杠（暗杠/补杠）：v1 不做（向听语义在杠后需重新评估，先保守）。

与 A2 的区别：A2 只在「是否听牌」二值上精确 + 静态分；SpeedA 用连续向听数
排序全部候选（深层也精确），是名符其实的“最快成型”基线。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .strategy import Strategy

W = "白"


def _melds_info(view):
    melds = view.get("melds") or []
    return len(melds), sum(1 for m in melds if m["type"] == "gang")


def _best_discard(hand, drawn, exposed, gangs):
    """弃牌：向听数最小 → 听牌等待数最大 → 保留刚摸。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs)) if s == 0 \
            else 0
        key = (s, -wcnt, -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


def _safe_discard(hand, drawn):
    """异常兜底弃牌：孤张字牌优先 → 首张（绝不抛）。"""
    for d in sorted(set(hand)):
        if d in HONOR:
            return d
    for d in hand:
        if d != drawn:
            return d
    return hand[0]


HONOR = set("东南西北中发白")


class SpeedA(Strategy):
    def __init__(self, name="speedA"):
        self.name = name

    def decide(self, view):
        offer = view.get("offer_tile")
        if window_pending(view) and offer:
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                return ({"action": "gang", "tile": offer} if cnt >= 3
                        else {"action": "peng", "tile": offer}
                        if cnt >= 2 else {"action": "pass", "tile": ""})
            return {"action": "pass", "tile": ""}
        if window_pending(view):
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
                    tile = _best_discard(hand, drawn, exposed, gangs)
                except ValueError:
                    # 防御：手牌形态与副露口径不一致（真机边缘）→ 安全弃牌
                    tile = _safe_discard(hand, drawn)
                return {"action": "discard", "tile": tile}
            return None
        return None
