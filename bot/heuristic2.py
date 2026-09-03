"""启发式策略 A2（教师迭代候选）：在 A 的静态牌型分之上加入听牌精确感知。

弃牌决策：对每个候选弃牌 →
  - 若弃后听牌：主键 0（越早听越好），次键 = 等待牌数（越多越好），
    再静态分（保结构）；
  - 否则：主键 1（未听），次键 = 静态分。
其余决策（胡/财飘/杠/窗口/抓打圈自检）与 HeuristicA 一致。
代价：每回合 ~10-20ms（听牌判定 13×34 次 is_win，进程级记忆化）；
作为「教师」离线生成样本用时可控（≈300-600 样本/s）。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits

from .heuristic import HeuristicA, _block_score


def _best_discard2(hand, drawn, exposed, gangs):
    """弃牌选择：听牌优先（含副露基准）+ 等待数 + 静态分。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            w = waits(rem, exposed_melds=exposed, gangs=gangs)
        except ValueError:                    # 防御：张数口径异常时不抛
            w = []
        key = (0, -len(w), -_block_score(rem)) if w else \
              (1, 0, -_block_score(rem))
        if d == drawn:
            key = (key[0], key[1], key[2] - 0.01)   # 同分偏留旧牌
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class HeuristicA2(HeuristicA):
    """听牌感知教师（窗口/胡/飘等行为继承 HeuristicA）。"""

    def __init__(self, name="heuristicA2"):
        super().__init__(name)

    def decide(self, view):
        from .model import my_turn, window_pending
        offer = view.get("offer_tile")
        if window_pending(view) and offer:
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                return ({"action": "gang", "tile": offer} if cnt >= 3
                        else {"action": "peng", "tile": offer}
                        if cnt >= 2 else {"action": "pass", "tile": ""})
            return {"action": "pass", "tile": ""}   # A2 吃窗口全过（保守）
        if window_pending(view):
            return {"action": "pass", "tile": ""}
        if my_turn(view):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            if drawn == "白" and view.get("god", {}).get("baotou"):
                return {"action": "discard", "tile": "白"}
            can_gang = view.get("can_gang", False)
            if can_gang and drawn:
                for t in sorted(set(hand)):
                    if t != "白" and hand.count(t) == 4:
                        return {"action": "gang", "tile": t}
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
                        "tile": _best_discard2(hand, drawn, exposed, gangs)}
            return None
        return None
