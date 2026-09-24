# -*- coding: utf-8 -*-
"""meld_ukeire_audit —— 吃/碰的**进张层**核对（§4c-45 提出的关键问题）。

`meld_offer_audit` 用**向听**给 offer 定价，但向听太粗：一次吃碰可能"向听不变"却让**进张变宽**。
本工具对每个 offer 算两个量：
  - `baseline_ukeire`：不吃不碰时的进张张数；
  - `take_ukeire`：接受后（拿走副露 + 从暗牌里打掉最优一张）的进张张数；
  - `delta = take − baseline`，并按 delta 分档统计**我方 vs 池内三对手的吃下率**。

**已测结果（60 份复盘 / 前 3 巡）**：进张 +7 以上的 offer 有 263 个，**我方只吃 11.4%，池内吃 20.8%**（差 −9.4pp）；
而"进张 ≤0"的 offer 我方 15.9% vs 池内 17.2%、"进张 +1~2"我方 27.3% vs 池内 21.6%。
⇒ **差异集中在"明显有益（+7 张以上）"的那一档**，而且是我们**更保守**；这与"我们只是更挑剔"的直觉相反。

**要回答的问题**：那两个比我们强的同池玩家（§4c-45：听牌率 54.6% vs 我方 46.2%、副露 1.15 vs 0.74）
是不是在吃"向听不变但进张变宽"的 offer？如果是——**那就是缺失的机制**；如果不是——副露结构这条也可以关掉。

⚠ **很慢**：每个 offer 的进张要枚举 ~30 张候选 × 每张 ~13 次向听 ⇒ 实测 **8 份/3 巡 ≈ 66 秒**、
30 份/3 巡 ≈ 4 分钟；**100 份/8 巡 会跑 20 分钟以上**（本轮因此放弃大样本，改用 30 份/3 巡的方向性结论）。

用法：python -X utf8 tools/meld_ukeire_audit.py --dirs recent --limit 30 --max-turn 3
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import importlib.util
spec = importlib.util.spec_from_file_location("moa2", os.path.join(ROOT, "tools", "meld_offer_audit.py"))
moa = importlib.util.module_from_spec(spec)
sys.modules["moa2"] = moa
spec.loader.exec_module(moa)
ME = moa.ME


def canon(hand, ex, gg):
    return moa._canon13(hand, ex, gg)


def uke_after_one(hand, tile, kind, ex, gg):
    """接受该 offer 后的进张张数。

    ⚠ 规格说明（这里是之前全 0 的根因）：**吃/碰之前**玩家的暗牌是 13 张规格
    （`need(ex) = 3*(4-ex)+1-gg`）；**吃/碰之后**亮出一组面子，暗牌变成 12 张，
    而此时"进张"应相对"等摸一张"的 11 张规格来算。所以这里先减到 11 张再调 ukeire。
    """
    h = canon(hand, ex, gg)
    if kind == "peng":
        if h.count(tile) < 2:
            return None
        h.remove(tile)
        h.remove(tile)
    else:
        p = moa._parse(tile)
        if not p or p[0] == "h":
            return None
        suit, rank = p
        got = None
        for a, b in ((rank - 2, rank - 1), (rank - 1, rank + 1), (rank + 1, rank + 2)):
            ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
            if a < 1 or b > 9 or h.count(ta) < 1 or h.count(tb) < 1:
                continue
            hh = list(h)
            hh.remove(ta)
            hh.remove(tb)
            got = hh
            break
        if got is None:
            return None
        h = got
    # 此时暗牌 = need(ex) - 2 = need(ex+1) - 1 ⇒ 再打掉一张，变成等摸的规格
    best = None
    for t in set(h):
        hh = list(h)
        hh.remove(t)
        v = moa.ukeire(hh, ex + 1, gg)
        if v is None:
            continue
        best = v if best is None else max(best, v)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="recent")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-turn", type=int, default=6)
    a = ap.parse_args(argv)
    files = []
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        files += glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json"))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]
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
        pending = {}
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
                    for o in range(4):
                        if o == s or hands[o] is None or turn[o] >= a.max_turn:
                            continue
                        ex, gg = nm[o] + ng[o], ng[o]
                        base_sh = moa.sh(list(hands[o]), ex, gg)
                        if base_sh is None:
                            continue
                        h = canon(hands[o], ex, gg)
                        base_u = moa.ukeire(h, ex, gg)
                        ups = [v for v in (uke_after_one(hands[o], tile, "peng", ex, gg),
                                            uke_after_one(hands[o], tile, "chi", ex, gg)) if v is not None]
                        if base_u is None or not ups:
                            continue
                        delta = max(ups) - base_u
                        if delta <= 0:
                            bucket = "same_or_narrower"
                        elif delta <= 2:
                            bucket = "wider_1_2"
                        elif delta <= 6:
                            bucket = "wider_3_6"
                        else:
                            bucket = "wider_7plus"
                        side = "me" if o == me else "pool"
                        stat[bucket][side][0] += 1
                        pending[o] = (bucket, side)
                    if tile in hands[s]:
                        hands[s].remove(tile)
                    turn[s] += 1
                    pending.pop(s, None)
                elif t in ("pass", "timeout"):
                    pending.pop(s, None)
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
    print("吃/碰 进张层核对（语料 %d 份；前 %d 巡）" % (len(files), a.max_turn))
    print("档位 = 接受后的进张 − 不吃不碰的进张（按增量分档：7+/3-6/1-2/≤0）")
    print("-" * 78)
    print("%-10s %14s %10s %14s %10s" % ("档位", "我方 offer", "吃下率", "池内 offer", "吃下率"))
    names = {"wider_7plus": "进张+7以上", "wider_3_6": "进张+3~6",
             "wider_1_2": "进张+1~2", "same_or_narrower": "进张≤0(无益/变窄)"}
    for bucket in ("wider_7plus", "wider_3_6", "wider_1_2", "same_or_narrower"):
        m = stat[bucket].get("me", [0, 0])
        o = stat[bucket].get("pool", [0, 0])
        mr = 100.0 * m[1] / m[0] if m[0] else 0.0
        orr = 100.0 * o[1] / o[0] if o[0] else 0.0
        print("%-16s %12d %9.1f%% %12d %9.1f%%" % (names[bucket], m[0], mr, o[0], orr))
    print("=" * 78)


if __name__ == "__main__":
    main()
