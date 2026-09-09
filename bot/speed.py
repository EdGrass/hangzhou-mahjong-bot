"""速度策略引擎基类 SpeedBase —— 向听数驱动（SpeedB/E/F 的共同父类）。

（竞技策略 SpeedA 已退役：纯向听+无条件副露的组合被 SpeedB 副露收益判据
与 SpeedE 孤字优先取代；本文件保留为继承引擎——可胡即胡、向听最小、
听牌等待最大、副露直杠/碰即要 等原始决策逻辑，子类在其上覆盖窗口/选张。）

决策（顺序自检）：
1) 可胡即胡（含爆头摸白——纯速度不做财飘/打点绕路）；
2) 出牌：主键 = 弃后【精确向听数】（含财神/副露；越小越好），
   次键 = 若听牌【等待牌数】越多越好（ukeire），再次 = 抓打圈强制刚摸牌；
   同分偏好保留刚摸的牌；
3) 窗口：可直杠/碰就要；吃全过；
4) 自杠（暗杠/补杠）：不做（向听语义在杠后需重新评估，先保守）。
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



def _min_shanten_after_discard(hand, exposed, gangs):
    """弃 1 张后能达到的最小向听；长度不匹配（真机边缘）→ 99。"""
    best = 99
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            sv = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
        except ValueError:
            continue
        if sv < best:
            best = sv
            if best == 0:
                break
    return best


def _claim_value(hand, offer, kind, exposed, gangs, chi_pair=None):
    h = list(hand)
    if kind == "peng":
        if h.count(offer) < 2:
            return 99
        for _ in range(2):
            h.remove(offer)
        return _min_shanten_after_discard(h, exposed + 1, gangs)
    if kind == "gang_ming":
        if h.count(offer) < 3:
            return 99
        for _ in range(3):
            h.remove(offer)
        return _min_shanten_after_discard(h, exposed + 1, gangs + 1)
    if kind == "chi":
        if not chi_pair:
            return 99
        for t in chi_pair:
            if t not in h:
                return 99
            h.remove(t)
        return _min_shanten_after_discard(h, exposed + 1, gangs)
    return 99


def _chi_pairs(hand, offer):
    """吃牌可用组合（与引擎口径一致：同花差1/差2邻接）。"""
    if offer == W or offer[-1] not in "wbt":
        return []
    n = int(offer[0])
    suit = offer[1]
    hset = set(hand)
    out = []
    for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
        ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
        if 1 <= a <= 9 and 1 <= b <= 9 and ta in hset and tb in hset:
            out.append([ta, tb])
    return out


def _want_claim(view, kind):
    """副露收益判据：副露后成型是否更快（after < before）。真机长度不匹配
    时保守跳过（返回 False）。"""
    offer = view.get("offer_tile")
    if not offer:
        return False
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    if len(hand) != 13 - 3 * exposed - gangs:
        return False            # 副露计数与快照不同步（真机边缘）→ 不副露
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        before = 99
    if before == 0:
        return False            # 已听：保留听形
    if kind == "chi":
        # v25（2026-09-08）：服务端补齐「吃最多 2 摊」校验——同一局已有 2 组
        # 吃后第 3 次 chi 被 409；策略层先自限（防 harmful 409）
        chi_cnt = sum(1 for m in (view.get("melds") or [])
                      if isinstance(m, dict) and m.get("type") == "chi")
        if chi_cnt >= 2:
            return False
        best = 99
        for pair in _chi_pairs(hand, offer):
            v = _claim_value(hand, offer, "chi", exposed, gangs, pair)
            if v < best:
                best = v
        return best < before
    v = _claim_value(hand, offer, kind, exposed, gangs)
    return v < before


class SpeedBase(Strategy):
    def __init__(self, name="speedBase"):
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

class SpeedCore(SpeedBase):
    """SpeedBase + 副露收益判定（碰/杠/吃仅在更快成型时响应）。"""

    def decide(self, view):
        offer = view.get("offer_tile")
        if window_pending(view) and offer:
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and _want_claim(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and _want_claim(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi" and _want_claim(view, "chi"):
                return {"action": "chi", "tile": offer}
            return {"action": "pass", "tile": ""}
        return super().decide(view)
