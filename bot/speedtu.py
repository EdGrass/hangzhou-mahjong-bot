# -*- coding: utf-8 -*-
"""C019 SpeedTU —— SpeedTM + 听牌升级副露（tenpai upgrade）。

动机（2026-09-10，实测证据链）：
- 修复 409 后我方听牌率已到 48.1%（冠军 53.5%），但**听牌→胡转化 35% vs 51%**、
  **爆头态 0% vs 5.4%**；
- 死听不是原因（我方 0%、冠军 0.1-0.3%）；等待宽度也不是（活等副本 7.47 vs 8.91）；
- 引擎自检（var/_baotou_engine.py）证明：e=3 副露 + 暗手「1 面子 + 白孤」被
  正确判为 **shanten 0 / waits 34 / is_baotou=True**，且弃牌评分正确优先它；
- **真正的堵点**：e=2 时那手 7 张（含对子+白）**已经 shanten 0**，而 SpeedE/M/TM
  的窗口判据都是「已听（before<=0）不副露」→ 亲手拒掉了那次把 e→3、进而
  落进爆头（34 张万能听 + ×2 番）的副露。
- 又因**自摸和**：副露到 e=3 后那手 5 张虽是「面子+对子」成胡形，也不能胡，
  只能弃牌 → 正好弃成「面子+白孤」= 爆头。这是副露独有的换听窗口。

与 SpeedTM 的唯一差异 = 已听状态下的窗口判据：
  before > 0 → 沿用 TM 的 mild 判据（after <= before 即接受）；
  before == 0 → **仅当副露后（含最优弃牌）仍是听牌且等待张数严格变多**
                才接受（爆头 34 张必然通过）。即「换听升级」而非「已听不动」。
其余 100% 继承（出牌 = SpeedT；吃/碰上限、抓打圈、胡 = SpeedE）。
"""
from __future__ import annotations

from mahjong.hu import is_baotou, is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedm import want_claim_mild
from .speedt import _best_discard_t
from .speede import SpeedE


def _best_after_claim(hand, exposed, gangs, kind, offer, pair=None):
    """模拟 claim + 最优弃牌，返回 (key, tile, shanten, waits, is_baotou) 或 None。"""
    h = list(hand)
    if kind == "peng":
        if h.count(offer) < 2:
            return None
        for _ in range(2):
            h.remove(offer)
        e, g = exposed + 1, gangs
    elif kind == "gang_ming":
        if h.count(offer) < 3:
            return None
        for _ in range(3):
            h.remove(offer)
        e, g = exposed + 1, gangs + 1
    elif kind == "chi":
        if not pair:
            return None
        for t in pair:
            if t not in h:
                return None
            h.remove(t)
        e, g = exposed + 1, gangs
    else:
        return None
    best = None
    for d in sorted(set(h)):
        rem = list(h)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(e == 0 and g == 0),
                              exposed_melds=e, gangs=g)
            if s == 0:
                w = len(waits(rem, exposed_melds=e, gangs=g))
                bb = is_baotou(rem, allow_qidui=(e == 0 and g == 0),
                               exposed_melds=e, gangs=g)
            else:
                w, bb = 0, False
        except ValueError:
            continue
        key = (s, -w, 0 if bb else 1)
        if best is None or key < best[0]:
            best = (key, d, s, w, bb)
    return best


def want_claim_upgrade(view, kind, pair=None):
    """窗口判据：未听用 TM mild；已听则只在能换成更宽听形时副露。"""
    offer = view.get("offer_tile")
    if not offer:
        return False
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    if len(hand) != 13 - 3 * exposed - gangs:
        return False
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return False
    if before > 0:
        return want_claim_mild(view, kind)
    # 已听：仅接受「换听升级」
    after = _best_after_claim(hand, exposed, gangs, kind, offer, pair)
    if after is None:
        return False
    _, _, s_after, w_after, _bb = after
    if s_after != 0:
        return False
    try:
        w_before = len(waits(hand, exposed_melds=exposed, gangs=gangs))
    except ValueError:
        return False
    return w_after > w_before


class SpeedTU(SpeedE):
    def __init__(self, name="speedTU"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_upgrade(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and want_claim_upgrade(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi":
                hand = list(view["my_hand"])
                exposed, gangs = _melds_info(view)
                chi_cnt = sum(1 for m in (view.get("melds") or [])
                              if isinstance(m, dict) and m.get("type") == "chi")
                if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:
                    for pair in _chi_pairs(hand, offer):
                        if want_claim_upgrade(view, "chi", pair):
                            return {"action": "chi", "tile": offer}
                return {"action": "pass", "tile": ""}
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
