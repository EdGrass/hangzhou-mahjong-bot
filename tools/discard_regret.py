# -*- coding: utf-8 -*-
"""discard_regret —— 逐决策的「出牌遗憾」核对（用现成的向听函数，不靠代理指标）。

回答一个问题：**第 1~N 巡里，我们实际打出的那张牌，是不是"打完向听最小、再在并列里选听牌最宽"的那张？**

口径（每一步都可复算）：
  - 数据 = 门户全信息复盘 `var/replays/{server,recent}/*.json`（四家起手 + 全部事件）；
  - 对**我方**的每次出牌（巡次 <= N）：重建手牌 → 对每个候选弃牌算
    `exact_shanten(剩下12张)`；取最小向听组，再用 `waits()` 的进张张数做 tiebreak；
  - **regret = (实际牌的价值) 比 (最优牌的价值) 差多少**，分三档：
      `none`（就是最优之一） / `shanten+1`（向听多一层：明显错） / `narrower`（向听相同但听牌更窄）。

为什么需要：`ab_mechanism.py` 与 `discard_profile.py` 用的是**真进张**等更贵的口径；本工具用**最便宜的确定性规则**
给出一条"和我们自己的判据对齐"的 regret 基线，用来判断**候选改动到底改了多少决策**（而不是猜）。

用法：
    python -X utf8 tools/discard_regret.py                # 第 1~8 巡
    python -X utf8 tools/discard_regret.py --max-turn 4
    python -X utf8 tools/discard_regret.py --by-strategy    # 按 auto_ranking 的策略归属分组
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402
from mahjong.shanten import waits                            # noqa: E402

ME = "u_7a3fba48d70b"


def _strategies():
    m = {}
    p = os.path.join(ROOT, "var", "auto_ranking.jsonl")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("room"):
                m[d["room"]] = d.get("strategy") or "?"
    return m


def best_discards(hand, exposed, gangs):
    """返回 (best_shanten, best_width, {tile: (shanten, width)}) —— 纯函数，可单测。"""
    qidui = (exposed == 0 and gangs == 0)
    seen = []
    for t in sorted(set(hand)):
        rest = list(hand)
        rest.remove(t)
        try:
            sh = exact_shanten(rest, qidui=qidui, exposed_melds=exposed, gangs=gangs)
        except Exception:
            continue
        try:
            w = len(waits(rest, exposed_melds=exposed, gangs=gangs)) if sh == 0 else 0
        except Exception:
            w = 0
        seen.append((t, sh, w))
    if not seen:
        return None, None, {}
    bs = min(x[1] for x in seen)
    bw = max(x[2] for x in seen if x[1] == bs)
    return bs, bw, {t: (sh, w) for t, sh, w in seen}


def classify(actual, best):
    """actual/best = (shanten, width)；返回 none / shanten+1 / narrower / unknown。"""
    if actual is None or best is None:
        return "unknown"
    if actual[0] > best[0]:
        return "shanten+1"
    if actual[0] == best[0] and actual[1] < best[1]:
        return "narrower"
    return "none"


def scan(path, max_turn=8):
    """返回 list[(room, turn, tile, actual, best, bucket)]（只含我方出牌）。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    ids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
    if ME not in ids or len(ids) != 4:
        return None
    me = ids.index(ME)
    hands = [None] * 4
    nm = [0] * 4
    ng = [0] * 4
    turn = [0] * 4
    out = []
    for b in d.get("blocks") or []:
        sh0 = b.get("start_hands")
        if sh0 and any(isinstance(x, (list, tuple)) for x in sh0):
            hands = [list(x) if isinstance(x, (list, tuple)) else [] for x in sh0]
            nm = [0] * 4
            ng = [0] * 4
            turn = [0] * 4
        if hands[0] is None:
            continue
        for e in b.get("events") or []:
            t, s = e.get("type"), e.get("seat")
            if t == "round_ended":
                hands = [None] * 4
                continue
            if s is None or s < 0 or hands[s] is None:
                continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
            elif t == "tile_discarded":
                tile = e.get("tile")
                if s == me and tile in hands[s]:
                    turn[s] += 1
                    if turn[s] <= max_turn:
                        ex, gg = nm[s] + ng[s], ng[s]
                        bs, bw, table = best_discards(list(hands[s]), ex, gg)
                        actual = table.get(tile)
                        best = (bs, bw) if bs is not None else None
                        out.append((tile, actual, best, classify(actual, best), turn[s]))
                if tile in hands[s]:
                    hands[s].remove(tile)
            elif t == "peng":
                for _ in range(2):
                    if e.get("tile") in hands[s]:
                        hands[s].remove(e.get("tile"))
                nm[s] += 1
            elif t == "chi":
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
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turn", type=int, default=8)
    ap.add_argument("--dirs", default="server,recent")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--by-strategy", action="store_true")
    a = ap.parse_args(argv)
    smap = _strategies() if a.by_strategy else {}
    files = []
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        files += glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json"))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]
    buckets = collections.Counter()
    by_strat = collections.defaultdict(collections.Counter)
    by_turn = collections.defaultdict(collections.Counter)
    for p in files:
        rows = scan(p, max_turn=a.max_turn)
        if not rows:
            continue
        room = os.path.basename(p).split("_r")[0]
        st = smap.get(room, "?")
        for _tile, _act, _best, bucket, tn in rows:
            buckets[bucket] += 1
            by_strat[st][bucket] += 1
            by_turn[tn][bucket] += 1
    tot = sum(buckets.values())
    print("=" * 78)
    print("出牌遗憾核对（第 1~%d 巡；语料 %d 份复盘；我方出牌样本 %d）" % (a.max_turn, len(files), tot))
    print("⚠ 本工具的「最优」= min(普通形, 七对形) 的向听，而我方 bot 走的是普通形 ⇒")
    if not tot:
        print("（无样本）")
        return
    names = {"none": "最优之一", "narrower": "向听同但更窄", "shanten+1": "向听多一层", "unknown": "无法判定"}
    for k in ("none", "narrower", "shanten+1", "unknown"):
        if buckets.get(k):
            print("  %-12s %8d  %5.2f%%" % (names[k], buckets[k], 100.0 * buckets[k] / tot))
    print("  ⇒ 非最优合计 %.2f%%" % (100.0 * sum(v for k, v in buckets.items() if k != "none") / tot))
    print()
    print("  按巡次：")
    for tn in sorted(by_turn):
        c = by_turn[tn]
        n = sum(c.values())
        bad = sum(v for k, v in c.items() if k != "none")
        print("    第 %d 巡: %5d 样本，非最优 %5.1f%%（向听+1 %4.1f%%）"
              % (tn, n, 100.0 * bad / max(n, 1), 100.0 * c.get("shanten+1", 0) / max(n, 1)))
    if a.by_strategy:
        print()
        print("  按策略：")
        for st in sorted(by_strat):
            c = by_strat[st]
            n = sum(c.values())
            if n < 50:
                continue
            bad = sum(v for k, v in c.items() if k != "none")
            s1 = c.get("shanten+1", 0)
            print("    %-16s %6d 样本  非最优 %5.1f%%  向听+1 %4.1f%%"
                  % (st, n, 100.0 * bad / n, 100.0 * s1 / n))
    print("=" * 78)


if __name__ == "__main__":
    main()
