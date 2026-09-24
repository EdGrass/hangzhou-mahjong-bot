# -*- coding: utf-8 -*-
"""C018 SpeedTMA —— SpeedT + 无门控副露（M 的进一步放宽）。

动机（2026-09-10，执行层修复后的真机数据）：
- 修 409 前我方落地副露 0.198/局（冠军 1.2-1.5），听牌率 37.2%；
- 修 409 后落地副露 0.963/局，听牌率 41.2%、均听巡 7.69→5.61；
- 同房对照：副露 1.26-1.51/局的对手听牌 53.8-57.5%，我方 0.96/局仅 41.2%
  → 副露量仍是主要瓶颈；
- sim 档位扫描（1 席候选 vs 3 席 TM，各 320 局）：副露 0.96/局 → 听牌 59.1%，
  1.49/局 → 听牌 68.8%、均听巡 5.05、胡率 26.9% → 无门控档位最优。

与 SpeedTM 的唯一差异 = 窗口判据：不再要求「副露后向听不恶化」
（after<=before），只要**未听**（before>0，保留听形不拆）且形合法就吃/碰/杠。
吃仍自限 ≤2 摊（v25 服务端强制）。其余 100% 继承（出牌 = SpeedT；
胡/抓打圈/杠等 = SpeedE）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedt import _best_discard_t
from .speede import SpeedE


def _claim_ok(view):
    """无门控副露的前置校验：形合法且当前未听（返回 (hand, before) 或 None）。"""
    offer = view.get("offer_tile")
    if not offer:
        return None
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    if len(hand) != 13 - 3 * exposed - gangs:
        return None            # 快照与副露计数不同步 → 保守不副露
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return None
    if before <= 0:
        return None            # 已听：保留听形，不副露（与 TM 一致）
    return hand, exposed, gangs


class SpeedTMA(SpeedE):
    def __init__(self, name="speedTMA"):
        super().__init__(name)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            ok = _claim_ok(view)
            if ok is not None:
                hand, exposed, gangs = ok
                cnt = hand.count(offer)
                if view["phase"] == "response_peng":
                    if cnt >= 3:
                        return {"action": "gang", "tile": offer}
                    if cnt >= 2:
                        return {"action": "peng", "tile": offer}
                if view["phase"] == "response_chi":
                    chi_cnt = sum(1 for m in (view.get("melds") or [])
                                  if isinstance(m, dict)
                                  and m.get("type") == "chi")
                    if chi_cnt < 2 and _chi_pairs(hand, offer):
                        return {"action": "chi", "tile": offer}
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
