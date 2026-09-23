# -*- coding: utf-8 -*-
"""SpeedTUGH —— C061 候选：副露门控分档（向听<=2 mild，向听>=3 strict）。

对照当前生产 SpeedTUGC(C045)：未听时一律要求严格降向听。
本候选只在「已经接近听牌（向听 1~2）」时允许 after<=before 的等向听副露，
向听>=3 仍要求严格下降；已听仍继承 C019 换听升级，其余 100% 继承 SpeedTUG。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedm import want_claim_mild
from .speedt import _best_discard_t
from .speedtu import _best_after_claim
from .speedtug import SpeedTUG

MILD_UPTO = 2


def want_claim_tiered(view, kind, pair=None, mild_upto=MILD_UPTO):
    """向听<=mild_upto 允许 mild；向听>mild_upto 必须严格；已听走 C019。"""
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
        return want_claim_mild(view, kind, allow_equal=(before <= mild_upto))
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


class SpeedTUGH(SpeedTUG):
    def __init__(self, name="SpeedTUGH"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_tiered(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and want_claim_tiered(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi":
                hand = list(view["my_hand"])
                exposed, gangs = _melds_info(view)
                chi_cnt = sum(1 for m in (view.get("melds") or [])
                              if isinstance(m, dict) and m.get("type") == "chi")
                if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:
                    for pair in _chi_pairs(hand, offer):
                        if want_claim_tiered(view, "chi", pair):
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
                return super().decide(view)
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
