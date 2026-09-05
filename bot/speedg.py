"""SpeedG —— SpeedF + 【已见牌扣减】变体。

理论缺口 #1（复盘分析提出）：waits/ukeire 目前只扣手牌占用，不扣牌河已见
——单钓"北"但场上已见 3 张时自摸概率为 0，仍被当 1 等待。SpeedG 把
tie 内 ukeire 与听牌等待全部按「剩余张数（4 - 手牌 - 已见）」修正：
- view['river']（game 层注入：全部公开弃牌 tile 列表）非空时生效
- 出牌：向听 → 等待（扣已见）→ 弃后 ukeire（候选排除已耗尽牌）
  → 孤字 → 保留刚摸
其余决策继承 SpeedF（副露收益判据）。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import HONOR
from .speedf import SpeedF, _candidate_tiles


def _seen_of(hand, river):
    """已见占用统计：手牌 + 公开弃牌河。"""
    seen = {}
    for t in list(hand) + (river or []):
        seen[t] = seen.get(t, 0) + 1
    return seen


def _ukeire_river(rem, exposed, gangs, seen):
    """弃后 rem 的进张数（已见牌不可进张）。"""
    try:
        cur = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                            exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return 0
    if cur <= 0:
        return 0
    cnt = 0
    for t in _candidate_tiles(rem):
        if seen.get(t, 0) >= 4:
            continue            # 已耗尽（含河）
        nt = rem + [t]
        improved = False
        for x in set(nt):
            cand = list(nt)
            cand.remove(x)
            try:
                s = exact_shanten(cand, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs)
            except ValueError:
                continue
            if s < cur:
                improved = True
                break
        if improved:
            cnt += 1
    return cnt


def _waits_river(hand13, exposed, gangs, seen):
    """听牌等待（按剩余张数，已见扣减）。"""
    w = waits(hand13, exposed_melds=exposed, gangs=gangs)
    return [t for t in w if seen.get(t, 0) < 4]


def _best_discard_river(hand, drawn, exposed, gangs, seen):
    """弃牌：向听 → 听牌等待(剩余) → 弃后 ukeire(已见) → 孤字 → 保留刚摸。"""
    groups = {}
    order = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        if s == 0:
            w = len(_waits_river(rem, exposed, gangs, seen))
        else:
            w = 0
        key = (s, -w)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(d)
    order.sort()
    for key in order:
        ds = groups[key]
        if key[0] == 1 and len(ds) > 1:
            best_d, best_uk = None, -1
            for d in ds:
                rem = list(hand)
                rem.remove(d)
                uk = _ukeire_river(rem, exposed, gangs, seen)
                if uk > best_uk:
                    best_uk, best_d = uk, d
            if best_d is not None:
                return best_d
        tie = sorted(ds, key=lambda d: (0 if d in HONOR else 1,
                                        -1 if d == drawn else 0))
        return tie[0]
    return hand[0]


class SpeedG(SpeedF):
    def __init__(self, name="speedG"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view) and view.get("drawn_tile"):
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
                river = view.get("river") or []
                seen = _seen_of(hand, river)
                try:
                    tile = _best_discard_river(hand, drawn, exposed, gangs,
                                               seen)
                except Exception:
                    tile = _safe(hand, drawn)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)


def _safe(hand, drawn):
    for d in sorted(set(hand)):
        if d in HONOR:
            return d
    for d in hand:
        if d != drawn:
            return d
    return hand[0]
