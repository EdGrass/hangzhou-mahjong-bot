"""启发式策略 A（首版可用实现）。

决策：
- 摸牌后可胡 → 立即 hu（v1 不做弃胡/飘博弈，链与窗口等模拟器 v2）；
- 否则选弃牌：静态牌型评分（零搜索，µs 级）——拆解弃某张后的 13 张手牌，
  得分 = 完整面子 ×4 + 对子 ×2 + 顺子残形 ×1.5 + 财神保留奖励 − 孤张惩罚，
  选得分最高的弃法；同分偏好弃刚摸的牌；
- 窗口阶段 v1 不响应（协议层视同 pass）。

静态评分是骨架期基线；min_swaps/waits 搜索式评估待模拟器向量化/批量化后接入。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.tiles import is_suit_tile, id_of, suit_and_num

from .model import my_turn, window_pending
from .strategy import Strategy


def _block_score(hand13):
    """13 张静态牌型分：面子/对子/残形/财神 权重和（不区分是否真能成型）。"""
    counts = [0] * 34
    for t in hand13:
        counts[id_of(t)] += 1
    score = 0.0
    jokers = counts[33]
    # 财神保留奖励：每张财神本身价值高（可补任意结构）
    score += jokers * 3.0
    for si in range(3):                      # 数牌花色
        c = counts[si * 9:(si + 1) * 9]
        i = 0
        while i < 9:
            if c[i] >= 3:
                score += 4.0                 # 刻子
                c[i] -= 3
                continue
            if i <= 6 and c[i] > 0 and c[i + 1] > 0 and c[i + 2] > 0:
                score += 4.0                 # 顺子
                c[i] -= 1; c[i + 1] -= 1; c[i + 2] -= 1
                continue
            i += 1
        # 残形：对子 2 分；顺子残形（相邻有牌）1.5/0.8 分
        i = 0
        while i < 9:
            if c[i] >= 2:
                score += 2.0
                c[i] -= 2
            elif c[i] == 1:
                adj = (i + 1 < 9 and c[i + 1] > 0) or \
                      (i + 2 < 9 and c[i + 2] > 0) or \
                      (i - 1 >= 0 and c[i - 1] > 0)
                score += 1.5 if adj else 0.6
                # 消耗相邻形成残形计数（简化：不回溯）
                if i + 1 < 9 and c[i + 1] > 0 and c[i] > 0:
                    pass
            i += 1
    for hi in range(27, 33):                 # 字牌
        c = counts[hi]
        if c >= 3:
            score += 4.0
        elif c == 2:
            score += 2.0
        elif c == 1:
            score += 0.4                     # 孤张字牌价值低
    return score


def _best_discard(hand14, drawn):
    """返回要弃的牌码：试弃每张不同牌面，取 13 张静态分最高者。"""
    best_tile, best_score = None, None
    for d in sorted(set(hand14)):
        rem = list(hand14)
        rem.remove(d)
        s = _block_score(rem)
        if d == drawn:
            s += 0.01                        # 同分偏留旧牌
        if best_score is None or s > best_score:
            best_score, best_tile = s, d
    return best_tile if best_tile is not None else hand14[0]


class HeuristicA(Strategy):
    """启发式策略 A（v2：副露窗口 + 自杠参与）。

    规则（骨架期基线，非最优）：
    - 摸牌后可胡 → 立即 hu；有自杠机会（4 张同码暗杠 / 碰组第 4 张补杠，
      白板禁杠、牌墙许可）→ 杠（吃动作链/杠上花机会）；
    - 窗口：可直杠/碰 → 要；下家可吃（未满 2 摊）→ 吃；
    - 否则静态牌型分弃牌（同 v1）。
    """

    def __init__(self, name="heuristicA"):
        self.name = name

    def decide(self, view):
        offer = view.get("offer_tile")
        if window_pending(view) and offer:
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3:
                    return {"action": "gang", "tile": offer}
                if cnt >= 2:
                    return {"action": "peng", "tile": offer}
            elif view["phase"] == "response_chi" and cnt >= 1:
                # 由引擎在 tiles 缺省时选第一组；这里显式不指定
                return {"action": "chi", "tile": offer}
        if window_pending(view):
            return {"action": "pass", "tile": ""}
        if my_turn(view):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            peng_t = [m["tile"] for m in melds if m["type"] == "peng"]
            drawn = view.get("drawn_tile")
            # 财飘：爆头态摸白 → 弃胡打白（chain+1/piao+1，仍听任意牌）
            if drawn == "白" and view.get("god", {}).get("baotou"):
                return {"action": "discard", "tile": "白"}
            can_gang = view.get("can_gang", False)
            if can_gang and drawn:
                # 仅摸牌后可自杠（副露后出牌态无杠权）
                for t in sorted(set(hand)):
                    if t != "白" and hand.count(t) == 4:
                        return {"action": "gang", "tile": t}
                for t in peng_t:
                    if t != "白" and t in hand:
                        return {"action": "gang", "tile": t}
            try:
                hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
            except ValueError:                # 真机快照无 melds 时按纯手牌
                hu = (exposed == 0 and gangs == 0) and is_win(hand)
            if hu and drawn:
                return {"action": "hu", "tile": ""}
            if hand:
                # 抓打圈内只能打刚摸的牌（服务端强校验，客户端先自检）
                if view.get("god", {}).get("catch_play") and drawn:
                    return {"action": "discard", "tile": drawn}
                return {"action": "discard",
                        "tile": _best_discard(hand, drawn)}
            return None
        return None
