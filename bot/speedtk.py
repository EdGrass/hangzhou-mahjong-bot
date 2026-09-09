# -*- coding: utf-8 -*-
"""SpeedTK —— SpeedT + K1(有效牌 ukeire tie) 组合（C015，2026-09-09）。

T（弃牌偏好：拆对后置/孤张优先）与 K1（同向听组内有效牌 ukeire 最大化）
各自独立给听牌率 +3~5pp（T 64.1 / U 62.5 vs E 58.9），从未组合——弃牌
评估全键：(向听 s, -ukeire/等待, -pref(弃牌偏好), 保留刚摸)。
窗口/副露判据 = SpeedE 原逻辑（可再叠加 M）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.shanten import waits

from .model import my_turn
from .speed import _best_discard
from .speedk import effective_tiles
from .speedt import SpeedT, _pref


def _best_discard_tk(hand, drawn, exposed, gangs):
    if not hand:
        return None
    drawn = drawn or None
    best_s = None
    cand = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            continue
        if best_s is None or s < best_s:
            best_s = s
            cand = [(s, d, rem)]
        elif s == best_s:
            cand.append((s, d, rem))
    if not cand:
        return _best_discard(hand, drawn, exposed, gangs)
    best_d, best_key = None, None
    for s, d, rem in cand:
        if s == 0:
            w = len(waits(rem, exposed_melds=exposed, gangs=gangs))
        else:
            w = effective_tiles(rem, exposed, gangs)
        key = (s, -w, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_d = key, d
    return best_d if best_d is not None else hand[0]


class SpeedTK(SpeedT):
    def __init__(self, name="speedTK"):
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
                    tile = _best_discard_tk(hand, drawn, exposed, gangs)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
