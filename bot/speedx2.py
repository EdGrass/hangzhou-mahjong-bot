"""SpeedX2 —— 自迭代候选 C002（实验名，未晋级不得作竞技默认）。

假设（docs/iter/queue.md C002，来源 PROJECT.md §7.5 / 理论缺口 #1，原 SpeedG
git 3c269fd 思路，曾与 F 一并被清、未获独立判定）：
waits/ukeire 只扣手牌占用、不扣牌河已见 → "单钓北但河已见 3" 仍被计 1 个活等待，
出牌 tie 与听牌取舍被死等污染。C002 把 SpeedE 的【听牌等待数】按
「剩余 = 4 − 手牌 − 公开河（view['river']）」修正，河见满 4 的牌不计等待。

与 SpeedE 的唯一差异：s==0（听牌）时的等待计数改为活等待（扣已见）；
无 river（或空河）时行为与 SpeedE 完全一致（含孤字/保留刚摸 tie 序）。
其余继承 SpeedE/SpeedCore（可胡即胡/抓打圈/副露判据/不暗杠）。

评估：sim 已注入 river（mahjong/sim.py，与真机 game.py 同口径）；
同桌面 speedx2x2+speedEx2，判据同 C001（δ_min=2，σ 实测，N≈1100+）。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import HONOR, SpeedCore, _best_discard  # noqa: F401
from .speede import SpeedE


def _seen_of(hand, river):
    """已见占用：手牌 + 公开弃牌河（口径同历史 SpeedG）。"""
    seen = {}
    for t in list(hand) + (river or []):
        seen[t] = seen.get(t, 0) + 1
    return seen


def _waits_live(rem13, exposed, gangs, seen):
    """听牌等待（按剩余张数扣已见；河见满 4 = 死等剔除）。"""
    out = []
    for t in waits(rem13, exposed_melds=exposed, gangs=gangs):
        if seen.get(t, 0) < 4:
            out.append(t)
    return out


def _best_discard_seen(hand, drawn, exposed, gangs, seen):
    """弃牌：向听最小 → 活等待最多 → 孤张字牌优先 → 保留刚摸（同 SpeedE 序）。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        wcnt = len(_waits_live(rem, exposed, gangs, seen)) if s == 0 else 0
        is_honor = d in HONOR
        key = (s, -wcnt, 0 if is_honor else 1, -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedX2(SpeedE):
    """候选 C002：SpeedE + 听牌等待扣已见（见模块 docstring）。"""

    def __init__(self, name="speedx2"):
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
                seen = _seen_of(hand, view.get("river"))
                try:
                    tile = _best_discard_seen(hand, drawn, exposed, gangs, seen)
                except ValueError:
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
