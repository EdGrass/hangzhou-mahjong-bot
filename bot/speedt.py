# -*- coding: utf-8 -*-
"""SpeedT —— SpeedE + 弃牌 tie 层修正（C012，复盘弃牌画像驱动，2026-09-09）。

动机（110 场自动房复盘弃牌画像，8126 vs 20287 次弃牌）：同向听组内——
我方拆对(DP) 11.7% vs 对手池 7.1%（+65%），弃孤中张(MS) 13.1% vs 20.8%、
孤边张(ES) 8.4% vs 12.9%——E 的 tie 只按牌面排序（≈随机），把"可做将/可
碰"的对子当废牌拆掉、留下难成搭的孤张 → 整局推进路径变长（自动房均听巡
7.8 vs 冠军 5.6-6.9）。

SpeedT 与 SpeedE 唯一差异 = 同向听组内的弃牌偏好（其余含孤字 tie 的旧键
全部保留在其后）：
  pref(d, hand) 越小越早弃：
    0 孤张字牌（无对）         —— 死张，最优先弃
    1 数牌孤张（count==1 且手内无同花 ±1/±2 邻接；含 1/9 边孤）
    2 拆顺（顺子拆边张仍成搭：弃后剩余仍含该张邻接成搭——由向听保证同组）
    3 拆对（数对/字对，count>=2）
    4 白板（保留为财神万能——除非必须弃）
  注：tie 组由主键（向听 s、听牌等待 -wcnt）先过滤，pref 只在组内生效；
  顺子自然拆（56 弃 6 使 5 孤 = 向听升）不会进同组，无需额外防御。

其余 100% 继承 SpeedE（孤字 tie 已被 pref 吸收、保留刚摸仍在末键）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn
from .speed import HONOR
from .speede import SpeedE


def _pref(d, hand):
    """弃牌偏好（纯函数）：越小越早弃。见模块 docstring。"""
    if d == "白":
        return 4
    if d in HONOR:                      # 字牌：对子（可做将/碰）后弃
        return 3 if hand.count(d) >= 2 else 0
    cnt = hand.count(d)
    if cnt >= 2:
        return 3                        # 拆对
    if cnt == 1:
        n, suit = int(d[0]), d[1]
        for dd in (-2, -1, 1, 2):
            nn = n + dd
            if 1 <= nn <= 9 and "%d%s" % (nn, suit) in hand:
                return 2                # 邻接在手 = 顺子拆（搭子成员）
        return 1                        # 无邻孤张（边/中）
    return 1


def _best_discard_t(hand, drawn, exposed, gangs, god_meld=True):
    """弃牌：主键向听最小 → 听牌等待最大 → 弃牌偏好 pref → 保留刚摸。

    god_meld=False（C013 白保留模式）：向听评估中白不补面子——弃牌路径
    保守化，白倾向留作万能听（爆头导向）。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = 0
        from mahjong.shanten_exact import shanten as exact_shanten
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs,
                          god_meld=god_meld)
        wcnt = 0
        if s == 0:
            from mahjong.shanten import waits
            wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
        key = (s, -wcnt, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedT(SpeedE):
    def __init__(self, name="speedT"):
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
                    tile = _best_discard_t(hand, drawn, exposed, gangs)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
