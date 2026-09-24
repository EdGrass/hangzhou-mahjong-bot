# -*- coding: utf-8 -*-
"""SpeedTUGW —— C062 真机候选：**持白时放宽副露**（朝「3 副露 + 白孤 = 爆头 34 张听」走）。

来源（2026-09-11，用户报告「一直 Nomad 虐」后的专项解剖 E042）：
- Nomad 真机画像：副露 **1.44/局**（我们 speedtugc 0.79）、听牌 **69.4%**（我们 48.1%）、
  胡 **36.9%**（我们 23.1%）、fan/胡 1.381；他们 38% 的副露手里有白。
- 强场(3×SpeedTUG) 5seed：C045(speedtugc) 0.409、**本候选 0.422**（+0.088 vs 基线）；
  混合场：C045 0.447、本候选 0.431（判平）→ 需真机 A/B 定夺。

与 SpeedTUGC 的唯一差异 = 未听时(before>0)的副露判据：
  SpeedTUGC：一律要求**向听严格下降**（strict）；
  本候选：  **持白** → 允许 mild(after<=before)；**无白** → 仍严格；
  已听(before==0) 仍用 C019 换听升级；C036 弃胡换爆头与出牌逻辑原样继承。
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


def want_claim_bai_mild(view, kind, pair=None):
    """未听：持白放宽(mild)/无白严格；已听：C019 换听升级。"""
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
        allow_equal = hand.count("白") >= 1
        return want_claim_mild(view, kind, allow_equal=allow_equal)
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


class SpeedTUGW(SpeedTUG):
    def __init__(self, name="speedTUGW"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_bai_mild(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and want_claim_bai_mild(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi":
                hand = list(view["my_hand"])
                exposed, gangs = _melds_info(view)
                chi_cnt = sum(1 for m in (view.get("melds") or [])
                              if isinstance(m, dict) and m.get("type") == "chi")
                if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:
                    for pair in _chi_pairs(hand, offer):
                        if want_claim_bai_mild(view, "chi", pair):
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
