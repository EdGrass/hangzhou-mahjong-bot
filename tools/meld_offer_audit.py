# -*- coding: utf-8 -*-
"""meld_offer_audit —— 吃/碰的**机会层**核对：每个 offer 在"向听收益"上值不值得吃，以及我们吃/不吃得对不对。

为什么需要：§4c-31 实测"我方看到的吃碰窗口比对手多 30~48%，但吃下的比例更低"，
但**没有回答"该不该吃"**。本工具给每个 offer 算一个**与策略无关的客观价值**：

  对每次「别人打出 X，我方手上有 2 张 X（碰）或能成顺（吃）」——
  模拟"接受"（拿走副露，再从剩余暗牌里打掉向听最差的一张）与"拒绝"（什么都不做）两种情形，
  比较两者的 **exact_shanten**（必要时并列用听牌张数 tiebreak）。

于是每个 offer 得到一档：
  - `help_ge2`：接受让向听少 2 层以上（几乎必吃）
  - `help_1`：少 1 层（一般该吃）
  - `same`：向听不变（看牌型，通常不吃）
  - `hurt`：接受反而让向听变差（几乎必拒）

输出**我方 vs 池内三对手**在每一档上的"实际接受率"。若我方在 `help_1`/`help_ge2` 上的接受率明显低于对手，
那才是真正的**机会层的缺陷**（而不是 §4c-31 那种"窗口数"的口径差）。

用法：
    python -X utf8 tools/meld_offer_audit.py --dirs recent --max-turn 8
    python -X utf8 tools/meld_offer_audit.py --dirs server,recent --by-seat
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402

ME = "u_7a3fba48d70b"


def _parse(t):                       # noqa: E402
    if not t:
        return None
    if t[-1] in "wbt":
        return (t[-1], int(t[:-1]))
    return ("h", t)


def ukeire(hand, ex, gg):
    """进张张数：对 13 形状的手，统计"摸到后向听下降"的牌的总张数（含字牌/白）。
    这是比向听更细的口径——**一次吃碰即使向听不变，也可能让进张变宽**（§4c-45 提出的假设）。"""
    from mahjong.shanten import FULL_TILES, waits
    h = list(hand)
    need = 3 * (4 - int(ex)) + 1 - int(gg)
    if len(h) == need + 1:                 # 含刚摸到的那张 ⇒ 先规范化到 13 形状
        best_h, best_v = None, None
        for t in sorted(set(h)):   # ★ 确定序：并列最优时不再依赖 set 迭代顺序
            hh = list(h)
            hh.remove(t)
            v = sh(hh, ex, gg)
            if v is None:
                continue
            if best_v is None or v < best_v:
                best_v, best_h = v, hh
        h = best_h if best_h is not None else h
    if len(h) != need:
        return None
    base = sh(h, ex, gg)
    if base is None:
        return None
    total = 0
    # 只枚举"可能有用"的牌（同花色相邻 ±2 + 手里已有的字牌）⇒ 比全 136 张快 4~8 倍，
    # 且不会漏掉任何能降低向听的牌（远张必然无效）。
    cand = set()
    for t in sorted(set(h)):   # ★ 确定序：并列最优时不再依赖 set 迭代顺序
        p0 = _parse(t)
        if not p0:
            continue
        if p0[0] == "h":
            cand.add(t)
            continue
        suit, rank = p0
        for d in range(-2, 3):
            r = rank + d
            if 1 <= r <= 9:
                cand.add("%d%s" % (r, suit))
    for t in sorted(cand):
        if h.count(t) >= 4:
            continue
        hh = h + [t]
        # 摸到后要从 14 张里打掉最优一张（向听最小）
        best = None
        for x in set(hh):
            h2 = list(hh)
            h2.remove(x)
            v = sh(h2, ex, gg)
            if v is None:
                continue
            best = v if best is None else min(best, v)
        if best is not None and best < base:
            total += 4 - h.count(t)
    return total


_SH_CACHE = {}


def _sh_cached(hand, ex, gg, qidui):
    """向听缓存：同一手牌在多个 offer / 多份复盘里会反复出现，缓存能省 3~10 倍时间。"""
    key = (tuple(sorted(hand)), int(ex), int(gg), bool(qidui))
    v = _SH_CACHE.get(key)
    if v is None:
        try:
            v = exact_shanten(list(hand), qidui=bool(qidui), exposed_melds=int(ex), gangs=int(gg))
        except Exception:
            v = -1                      # -1 = 算不出（缓存这个结果，避免反复试）
        if len(_SH_CACHE) > 400000:
            _SH_CACHE.clear()
        _SH_CACHE[key] = v
    return None if v == -1 else v


def sh(hand, ex, gg):
    """向听。⚠ 复盘里的 start_hands 有时是 **14 张**（含摸到的那张）——而 exact_shanten 只接受
    "3*(4-e)+1-g 张"的手牌 ⇒ 14 张会抛异常。这里对 14 张的情况退化为"逐张试打，取最小向听"，
    否则整局都会被跳过（本工具最初的 bug：所有 offer 统计全是 0）。"""
    h = list(hand)
    need = 3 * (4 - int(ex)) + 1 - int(gg)
    try:
        if len(h) == need:
            return _sh_cached(h, ex, gg, (ex == 0 and gg == 0))
        if len(h) == need + 1:
            best = None
            for t in sorted(set(h)):   # ★ 确定序：并列最优时不再依赖 set 迭代顺序
                hh = list(h)
                hh.remove(t)
                v = _sh_cached(hh, ex, gg, (ex == 0 and gg == 0))
                if v is None:
                    continue
                best = v if best is None else min(best, v)
            return best
        return exact_shanten(h, qidui=(ex == 0 and gg == 0), exposed_melds=ex, gangs=gg)
    except Exception:
        return None


def _canon13(hand, ex, gg):
    """把暗牌规范成"可接受吃碰前"的形状（长度 = 3*(4-e)+1-g）。
    复盘里 start_hands 有时是 14 张 ⇒ 先逐张试打取最优的那张扔掉。"""
    h = list(hand)
    need = 3 * (4 - int(ex)) + 1 - int(gg)
    if len(h) == need:
        return h
    if len(h) == need + 1:
        best, best_h = None, None
        for t in sorted(set(h)):   # ★ 确定序：并列最优时不再依赖 set 迭代顺序
            hh = list(h)
            hh.remove(t)
            v = sh(hh, ex, gg)
            if v is None:
                continue
            if best is None or v < best:
                best, best_h = v, hh
        return best_h if best_h is not None else h
    return h


def value_of_take(hand, tile, kind, ex, gg):
    """接受一个吃/碰之后的向听值（先把暗牌规范到 13 形状，再拿走 2 张）。
    返回 (shanten, 用掉的张数)；不可能/算不出时返回 (None, 0)。

    ★ 2026-09-16 修（**flaky 单测的根因**）：碰的可行性必须在**原始手牌**上判，
    不能在 `_canon13` 之后判 —— 14 张手牌规范化时要"扔掉一张"，而当多张并列最优时
    旧实现用 `set(h)` 迭代（**顺序随 PYTHONHASHSEED 变化**）⇒ 偶尔把要碰的那张扔掉，
    于是 `count(tile) < 2` 返回 None（实测：全量单测 5 次里翻了 1 次）。
    """
    if kind == "peng":
        if hand.count(tile) < 2:
            return None, 0
        need = 3 * (4 - int(ex)) + 1 - int(gg)
        h = _canon13(hand, ex, gg)
        if h.count(tile) < 2:
            # 14 张规整时要扔一张；若并列最优里有"要碰的那张"，就换成**保留本牌**的规整
            # （判"能不能碰"不该被一个任意的最优解否掉 —— 这正是 flaky 的来源）
            h = list(hand)
            while len(h) > need:
                for t in sorted(set(h)):
                    if t != tile:
                        h.remove(t)
                        break
                else:
                    break
        h.remove(tile)
        h.remove(tile)
        return sh(h, ex + 1, gg), 2
    h = _canon13(hand, ex, gg)
    p = _parse(tile)
    if not p or p[0] == "h":
        return None, 0
    suit, rank = p
    best = None
    for a, b in ((rank - 2, rank - 1), (rank - 1, rank + 1), (rank + 1, rank + 2)):
        ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
        if a < 1 or b > 9 or h.count(ta) < 1 or h.count(tb) < 1:
            continue
        hh = list(h)
        hh.remove(ta)
        hh.remove(tb)
        v = sh(hh, ex + 1, gg)
        if v is not None and (best is None or v < best):
            best = v
    return best, 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="recent")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-turn", type=int, default=8)
    a = ap.parse_args(argv)
    files = []
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        files += glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json"))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]

    # 统计：bucket -> side -> [offers, takes]
    stat = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        ids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
        if ME not in ids or len(ids) != 4:
            continue
        me = ids.index(ME)
        hands = [None] * 4
        nm = [0] * 4
        ng = [0] * 4
        turn = [0] * 4
        pending = {}          # seat -> (bucket) 最近一次"可以吃碰"的窗口（在同一轮里被 take 或 pass 清掉）
        for b in d.get("blocks") or []:
            sh0 = b.get("start_hands")
            if sh0 and any(isinstance(x, (list, tuple)) for x in sh0):
                hands = [list(x) if isinstance(x, (list, tuple)) else [] for x in sh0]
                nm = [0] * 4
                ng = [0] * 4
                turn = [0] * 4
                pending = {}
            if hands[0] is None:
                continue
            for e in b.get("events") or []:
                t, s = e.get("type"), e.get("seat")
                if t == "round_ended":
                    hands = [None] * 4
                    pending = {}
                    continue
                if s is None or s < 0 or hands[s] is None:
                    continue
                if t == "tile_drawn":
                    hands[s].append(e.get("tile"))
                elif t == "tile_discarded":
                    tile = e.get("tile")
                    # 对每个其他座位，评估该弃牌是否构成吃/碰窗口（只在前 max_turn 巡内）
                    for o in range(4):
                        if o == s or hands[o] is None or turn[o] >= a.max_turn:
                            continue
                        ex, gg = nm[o] + ng[o], ng[o]
                        base = sh(list(hands[o]), ex, gg)
                        if base is None:
                            continue
                        val_p, n_p = value_of_take(hands[o], tile, "peng", ex, gg)
                        val_c, n_c = value_of_take(hands[o], tile, "chi", ex, gg)
                        if val_p is None and val_c is None:
                            continue
                        vals = [v for v in (val_p, val_c) if v is not None]
                        v = min(vals)
                        gain = base - v
                        bucket = "help_ge2" if gain >= 2 else ("help_1" if gain == 1 else ("same" if gain == 0 else "hurt"))
                        side = "me" if o == me else "pool"
                        stat[bucket][side][0] += 1
                        pending[o] = (bucket, side)
                    if tile in hands[s]:
                        hands[s].remove(tile)
                    turn[s] += 1
                    pending.pop(s, None)     # 自己打牌，自己的窗口作废；别人的窗口等他们响应
                elif t in ("pass", "timeout"):
                    pending.pop(s, None)      # 响应过（拒/超时）⇒ 该窗口结束
                elif t in ("peng", "chi"):
                    if s in pending:
                        bucket, side = pending.pop(s)
                        stat[bucket][side][1] += 1
                    if t == "peng":
                        for _ in range(2):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
                        nm[s] += 1
                    else:
                        used = list((e.get("data") or {}).get("tiles") or [])
                        if e.get("tile") in used:
                            used.remove(e.get("tile"))
                        for x in used:
                            if x in hands[s]:
                                hands[s].remove(x)
                        nm[s] += 1
                elif t == "gang":
                    kind = (e.get("data") or {}).get("kind")
                    if kind == "bu":
                        if e.get("tile") in hands[s]:
                            hands[s].remove(e.get("tile"))
                        nm[s] -= 1
                        ng[s] += 1
                    else:
                        for _ in range(4 if kind == "an" else 3):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
                        ng[s] += 1

    print("=" * 78)
    print("吃/碰机会层核对（语料 %d 份；只算前 %d 巡）" % (len(files), a.max_turn))
    print("档位含义：接受后向听少 2+ / 少 1 / 不变 / 变差")
    print("-" * 78)
    print("%-10s %14s %10s %14s %10s" % ("档位", "我方 offer", "吃下率", "池内 offer", "吃下率"))
    for bucket in ("help_ge2", "help_1", "same", "hurt"):
        m = stat[bucket].get("me", [0, 0])
        o = stat[bucket].get("pool", [0, 0])
        mr = 100.0 * m[1] / m[0] if m[0] else 0.0
        orr = 100.0 * o[1] / o[0] if o[0] else 0.0
        print("%-10s %14d %9.1f%% %14d %9.1f%%" % (bucket, m[0], mr, o[0], orr))
    print("=" * 78)


if __name__ == "__main__":
    main()
