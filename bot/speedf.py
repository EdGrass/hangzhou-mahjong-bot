"""SpeedF —— tie 内【精确 ukeire 进张最大化】变体。

复盘证据链：TOP 玩家同向听 tie 90%+ 为「先弃孤张字牌」→ SpeedE（孤字二分）
已实证 +3.9/局 vs SpeedB。本变体把二分升级为**精确进张计数**：
  向听最小 → 听牌等待最大 → 【弃后手牌的进张数（摸 1 张即降向听的牌种数）
  最大】→ 保留刚摸。
仅在主键并列候选 >1 时计算 ukeire（成本受限：每候选 34 摸 × 弃牌枚举，
shanten 走全局缓存）；向听 ≥1 才启用（听牌 tie 由等待数已充分区分）。

其余决策继承 SpeedE（副露收益判据 + 孤字 tie 后备）。
"""
from __future__ import annotations

from functools import lru_cache

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import HONOR
from .speede import SpeedE


@lru_cache(maxsize=8192)
def _cur_shanten(rem_t, exposed, gangs):
    """rem 的当前向听（缓存）。"""
    return exact_shanten(list(rem_t), qidui=(exposed == 0 and gangs == 0),
                         exposed_melds=exposed, gangs=gangs)


@lru_cache(maxsize=16384)
def _can_improve(nt_t, exposed, gangs, cur):
    """14 张（摸后）是否存在弃牌使向听 < cur。"""
    for x in set(nt_t):
        if x == nt_t[-1]:
            continue            # 弃刚摸 = 回到原状，必然无改进
        cand = list(nt_t)
        cand.remove(x)
        try:
            s = exact_shanten(cand, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            continue
        if s < cur:
            return True
    return False


def _candidate_tiles(rem):
    """有效进张只可能出现在手牌邻域：同花色 ±2、字牌同种、差张。"""
    cand = set()
    for t in rem:
        if t == "白":
            continue
        if t in "东南西北中发白":
            cand.add(t)
            continue
        n, suit = int(t[0]), t[1]
        for m in range(max(1, n - 2), min(9, n + 2) + 1):
            cand.add("%d%s" % (m, suit))
    return cand


def _ukeire(rem, exposed, gangs):
    """弃后 rem（13-3e-g 张）的进张数：摸 1 张存在弃牌使向听下降的牌种数。"""
    rem_t = tuple(sorted(rem))
    try:
        cur = _cur_shanten(rem_t, exposed, gangs)
    except ValueError:
        return 0
    if cur <= 0:
        return 0
    cnt = 0
    for t in _candidate_tiles(rem):
        if rem.count(t) >= 4:
            continue            # 该牌 4 张全在自己手
        nt_t = tuple(sorted(rem_t + (t,)))
        if _can_improve(nt_t, exposed, gangs, cur):
            cnt += 1
    return cnt


def _best_discard_ukeire(hand, drawn, exposed, gangs):
    """弃牌：向听 → 等待 → 弃后 ukeire 进张最大 → 孤字 → 保留刚摸。"""
    groups = {}                 # (s, -w) -> [(d, rem)]
    order = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        w = len(waits(rem, exposed_melds=exposed, gangs=gangs)) if s == 0 \
            else 0
        key = (s, -w)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(d)
    # 按主键序取最优组
    order.sort()
    for key in order:
        ds = groups[key]
        # ukeire 决胜仅在 s==1（听牌前最后一步，同分候选常 ≥2）计算；
        # 更高向听的分歧由 SpeedE 次序（孤字优先）已覆盖，省算力
        if key[0] == 1 and len(ds) > 1:
            best_d, best_uk = None, -1
            for d in ds:
                rem = list(hand)
                rem.remove(d)
                uk = _ukeire(rem, exposed, gangs)
                if uk > best_uk:
                    best_uk, best_d = uk, d
            if best_d is not None:
                return best_d
        # 单候选/听牌/高向听 tie：继承 SpeedE 次序（孤字优先/保留刚摸）
        tie = sorted(ds, key=lambda d: (0 if d in HONOR else 1,
                                        -1 if d == drawn else 0))
        return tie[0]
    return hand[0]


class SpeedF(SpeedE):
    def __init__(self, name="speedF"):
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
                try:
                    tile = _best_discard_ukeire(hand, drawn, exposed, gangs)
                except Exception:
                    tile = _safe_fallback(hand, drawn)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)


def _safe_fallback(hand, drawn):
    for d in sorted(set(hand)):
        if d in HONOR:
            return d
    for d in hand:
        if d != drawn:
            return d
    return hand[0]
