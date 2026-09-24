# -*- coding: utf-8 -*-
"""**真·进张(ukeire)**：与 `bot/c069routes.py:ukeire_counts` 的关键区别是——**要看是否降低向听**。

2026-09-17：生产实现 `real_ukeire` 改为"下界剪枝"版（**可证明逐位等价**，见其 docstring）；
朴素版留作 `real_ukeire_reference`，供 `tests/test_ukeire_fast_equiv.py` 对拍。

定义（13 张手牌 H、副露 e、杠 g、向听 s）：
    t 是进张  ⇔  ∃d∈H 使 shanten(H − d + t) < s
    real_ukeire(H) = Σ_t live(t) · 1[t 是进张]
其中 live(t) = 4 − 可见张数（默认只看自家手牌；给了 visible 就一并扣弃牌河与四家副露）。

候选牌只取「相邻集合」（自家手牌 ∪ 同花色 ±1/±2 ∪ 白）：
任何能降低向听的 t 必然与手里某张牌成对/成顺，故这是**安全的超集**，可把 34 种降到 ~20 种。

⚠ 用途纪律（2026-09-16）：**这是"手牌结构"的度量，不是结果度量**。
它可以用来量"基线有没有把手牌打得更宽"，但**不能当优化目标直接上线**——
`speedc132` 的教训（最大化邻接代理 ⇒ 真机听牌率 13.3% vs 27.2%）表明：
任何中间量都必须先在**轨迹级**证明与结果同向。
"""
from __future__ import annotations

import collections
import time

from mahjong.shanten_exact import _qidui_shanten, _shanten_counts
from mahjong.shanten_exact import shanten as _shanten
from mahjong.tiles import TILE_IDS, counts_of, id_of, is_suit_tile, suit_and_num


def neigh_tiles(hand):
    """进张候选的超集：自家手牌 + 同花色 ±1/±2 + 白。"""
    out = set(hand)
    for t in set(hand):
        try:
            if is_suit_tile(id_of(t)):
                suit, num = suit_and_num(id_of(t))
                for dd in (-2, -1, 1, 2):
                    n = num + dd
                    if 1 <= n <= 9:
                        out.add("%d%s" % (n, "wbt"[suit]))
        except Exception:
            continue
    out.add("白")
    return out


def visible_counts(hand, river=None, all_melds=None):
    """可见张数（自家手牌 + 弃牌河 + 四家副露）。"""
    vis = collections.Counter(hand)
    if river:
        vis.update(river)
    if all_melds:
        for seat_melds in all_melds:
            for m in (seat_melds or []):
                tiles = m.get("tiles") if isinstance(m, dict) else None
                if not tiles and isinstance(m, dict) and m.get("tile"):
                    tiles = [m["tile"]] * (4 if m.get("type") == "gang" else 3)
                if tiles:
                    vis.update(tiles)
    return vis


def real_ukeire_reference(hand13, exposed=0, gangs=0, visible=None, god_meld=True):
    """**朴素参考实现**（逐 d 精确判定）。保留用于等价性对拍；生产走 `real_ukeire`。

    返回 (进张张数, 进张种数)。算不动时返回 (None, None)。
    """
    e, g = int(exposed or 0), int(gangs or 0)
    hand = list(hand13)
    try:
        s0 = _shanten(hand, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g, god_meld=god_meld)
    except Exception:
        return None, None
    vis = dict(visible) if visible else collections.Counter(hand)
    own = collections.Counter(hand)
    need = (e == 0 and g == 0)
    live_total = 0
    kinds = 0
    for t in neigh_tiles(hand):
        live = 4 - int(vis.get(t, 0))
        if live <= 0:
            continue
        ok = False
        for d in set(hand):
            hh = list(hand)
            hh.remove(d)
            hh.append(t)
            try:
                if _shanten(hh, qidui=need, exposed_melds=e, gangs=g, god_meld=god_meld) < s0:
                    ok = True
                    break
            except Exception:
                pass
        if ok:
            live_total += live
            kinds += 1
    return live_total, kinds


def _shanten_after_draw(hand14, exposed, gangs, god_meld):
    """`hand14` 作为"已摸牌未打牌"的**下界**向听（可证明 ≤ 任何单张弃牌后的向听）。

    依据：`_shanten_counts` 的分解集合是 `S` 所有"块划分"；
    `S − d` 的任一划分都是 `S` 的划分（那张 d 留作未用）
    ⇒ `_shanten_counts(S) ≤ _shanten_counts(S − d)` 对任意 d 成立。
    七对分支同理：`qidui(S) ≤ qidui(S − d)`（去掉一张只会让对数不增）。
    """
    c = list(counts_of(hand14))
    best = _shanten_counts(tuple(c), int(exposed or 0), int(gangs or 0), bool(god_meld))
    if not exposed and not gangs:
        q = _qidui_shanten(c)
        if q < best:
            best = q
    return best


def real_ukeire(hand13, exposed=0, gangs=0, visible=None, god_meld=True, deadline=None):
    """返回 (进张张数, 进张种数)。算不动或超过 deadline 时返回 (None, None)。

    deadline 是可选的 `time.monotonic()` 截止值；一旦到期，调用者**必须**
    放弃本次精确计算并回退（不要把 None 当 0）。默认 None 时与旧版逐位相同。

    与 `real_ukeire_reference` **逐位相同**，只是省掉无用进张的枚举。

    为什么快：原实现对每个候选 t 都做 `∃d: shanten(H−d+t) < s0`，
    无用 t 会**跑满 |hand| 次精确向听**（实测每决策 ~944 次 shanten 调用、
    p95=638ms、max=1.55s，正式赛 M=10 下被 GIL 放大成 >3s 尾延迟）。

    本版先用一次 `_shanten_after_draw` 拿到**可证明的下界** s14：
      · `s14 >= s0` ⇒ `min_d shanten(H−d+t) >= s14 >= s0` ⇒ **必然不是进张**，
        整条 ∃ 循环安全跳过（**这是证明，不是近似**）；
      · `s14 < s0` ⇒ 回落到原逐 d 精确判定，保证结果一字不差。
    """
    e, g = int(exposed or 0), int(gangs or 0)
    hand = list(hand13)
    if deadline is not None and time.monotonic() >= deadline:
        return None, None
    need = (e == 0 and g == 0)
    try:
        s0 = _shanten(hand, qidui=need, exposed_melds=e, gangs=g, god_meld=god_meld)
    except Exception:
        return None, None
    vis = dict(visible) if visible else collections.Counter(hand)
    live_total = 0
    kinds = 0
    for t in neigh_tiles(hand):
        if deadline is not None and time.monotonic() >= deadline:
            return None, None
        live = 4 - int(vis.get(t, 0))
        if live <= 0:
            continue
        try:
            s14 = _shanten_after_draw(hand + [t], e, g, god_meld)
        except Exception:
            s14 = -1                      # 算不动 ⇒ 不跳过，走原路径
        if s14 >= s0:
            continue
        if deadline is not None and time.monotonic() >= deadline:
            return None, None
        ok = False
        for d in set(hand):
            if deadline is not None and time.monotonic() >= deadline:
                return None, None
            hh = list(hand)
            hh.remove(d)
            hh.append(t)
            try:
                if _shanten(hh, qidui=need, exposed_melds=e, gangs=g, god_meld=god_meld) < s0:
                    ok = True
                    break
            except Exception:
                pass
        if ok:
            live_total += live
            kinds += 1
    return live_total, kinds
