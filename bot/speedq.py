# -*- coding: utf-8 -*-
"""SpeedQ —— 七对路线导向（C014，冠军番型结构驱动，2026-09-09）。

动机（复盘 fan_struct/bao 样本）：朱雀-5973 七对率 35%（fan 1.5）、国士无双
fan 1.72（爆头 44%，其中零副露爆头 34 例几乎全为 6对+白 七对形）；我们七对
率仅 10%（200 胡 20 例）、fan 1.10。七对 ×2 与爆头 ×2 叠乘是冠军打点主源。

机制：E 的 exact_shanten 每步取 min(一般形, 七对) 但无路线记忆——手牌在
两条路线间摇摆时（如 4 对 3 搭：两路线同向听），贪心按一般形弃牌丢对子，
七对潜力被反复放弃。SpeedQ = T 基础上加**路线锁定**：弃牌时若
七对全局向听 <= 一般形全局向听 + lead（lead 默认 1：允许提前半步转），
则按七对路径弃牌（只比较 _qidui_shanten，自然保对弃散）；否则走一般形
（= SpeedT 原逻辑）。七对路径天然保留白（白可补任意对 → 爆头潜力）。

其余（窗口判据等）继承 SpeedE/SpeedT。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten_exact import _qidui_shanten
from mahjong.tiles import counts_of

from .model import my_turn
from .speed import _best_discard
from .speedt import SpeedT, _best_discard_t, _pref


def _q_discard(hand, drawn):
    """七对路径弃牌：qidui 向听最小 + 弃牌偏好 tie。返回 tile。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        q = _qidui_shanten(counts_of(rem))
        key = (q, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


def _route(hand, exposed, gangs, lead):
    """路线选择：True=七对路径（无副露且 qidui 全局向听够近）。"""
    if exposed or gangs:
        return False
    if "白" not in hand and sum(1 for t in set(hand) if t != "白"
                                and hand.count(t) >= 2) < 4:
        return False                # 无白且对子不足：无七对潜力
    q_best = 99
    g_best = 99
    from mahjong.shanten_exact import shanten as S
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        q = _qidui_shanten(counts_of(rem))
        if q < q_best:
            q_best = q
        try:
            g = S(rem, qidui=False, exposed_melds=exposed, gangs=gangs)
        except ValueError:
            g = 99
        if g < g_best:
            g_best = g
    return q_best <= g_best + lead


class SpeedQ(SpeedT):
    """SpeedT + 七对路线锁定（lead 可调，默认 1）。"""

    def __init__(self, name="speedQ", lead=1):
        super().__init__(name)
        self.lead = int(lead)

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
                    if _route(hand, exposed, gangs, self.lead):
                        tile = _q_discard(hand, drawn)
                    else:
                        tile = _best_discard_t(hand, drawn, exposed, gangs)
                except Exception:
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
