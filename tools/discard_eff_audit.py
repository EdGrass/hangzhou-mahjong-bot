# -*- coding: utf-8 -*-
"""discard_eff_audit —— 用**可信四家重建**逐手评估弃牌牌效：我方 vs top32（同房）。

背景：R423 证明胡率缺口 68% 在"听牌率"。R314 曾想做本对照，因 dec 相位坑撤回。
本工具改用门户 blocks（start_hands + 全事件含各家摸牌）重建 ⇒ 无相位问题。

逐手指标（每个弃牌决策点，只算手牌齐全的局）：
  sh_best   该手可达最小向听（= 弃牌前真实向听）
  sh_act    实际弃牌后的向听
  bad       sh_act > sh_best（**把牌打坏**）
  uke_best  同向听层内可达最大真进张（bot 同一把尺子：real_ukeire）
  uke_act   实际弃牌的真进张
  uloss     uke_best - uke_act（仅在不打坏时计）

**控制项**：C036 弃胡换爆头会**故意**打坏向听，所以单独统计"弃牌前 14 张已可胡"的点，
并在第二阶段把它们排除，看剩余打坏率。

用法：python -X utf8 tools/discard_eff_audit.py [文件数，0=全部] [--json out]
"""
from __future__ import annotations
import collections, glob, json, os, ssl, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as SH          # noqa: E402
from mahjong.tiles import GOD_TILE                        # noqa: E402
from mahjong.hu import is_win                             # noqa: E402
from bot.ukeire import real_ukeire                        # noqa: E402
ME = "u_7a3fba48d70b"


def board_top(n=32):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, "var", ".portal_cookie"),
                  encoding="utf-8-sig").read().strip()
    req = urllib.request.Request(
        "<平台地址>/portal/api/leaderboard?period=all",
        headers={"Cookie": cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                   .read().decode("utf-8"))
    return {p["user_id"] for p in (d.get("top") or [])[:n]}


def audit_round(start_hands, events):
    """返回 [(seat, hand14, e, g, actual_discard, river_snapshot, menzen)]。"""
    hands = [list(h) for h in start_hands]
    melds = [[] for _ in range(4)]
    river = [collections.Counter() for _ in range(4)]
    last_drawn = [None] * 4
    meld_tiles = [collections.Counter() for _ in range(4)]
    out = []
    for e in events:
        t, s = e.get("type"), e.get("seat")
        if s is None:
            continue
        if t == "tile_drawn":
            if e.get("tile"):
                hands[s].append(e["tile"])
                last_drawn[s] = e["tile"]
        elif t == "tile_discarded":
            tile = e.get("tile")
            cp = bool((e.get("data") or {}).get("catch_play"))
            if tile and tile in hands[s]:
                e_cnt = sum(1 for m in melds[s] if not m.get("gang"))
                g_cnt = sum(1 for m in melds[s] if m.get("gang"))
                if len(hands[s]) == 14 - 3 * e_cnt - g_cnt and len(set(hands[s])) > 1:
                    out.append((s, list(hands[s]), e_cnt, g_cnt, tile,
                                [collections.Counter(r) for r in river],
                                e_cnt == 0 and g_cnt == 0, cp, e.get("seq"),
                                last_drawn[s],
                                [collections.Counter(x) for x in meld_tiles]))
                hands[s].remove(tile)
                river[s][tile] += 1
        elif t == "chi":
            for x in (e.get("data") or {}).get("tiles") or []:
                if x != e.get("tile") and x in hands[s]:
                    hands[s].remove(x)
            melds[s].append({"gang": False})
            for x in (e.get("data") or {}).get("tiles") or []:
                meld_tiles[s][x] += 1
            if e.get("tile"):
                river[s][e["tile"]] += 1
        elif t == "peng":
            for _ in range(2):
                if e.get("tile") in hands[s]:
                    hands[s].remove(e["tile"])
            melds[s].append({"gang": False})
            for _ in range(3):
                meld_tiles[s][e.get("tile")] += 1
            if e.get("tile"):
                river[s][e["tile"]] += 1
        elif t == "gang":
            kind, tl = (e.get("data") or {}).get("kind"), e.get("tile")
            if kind == "bu":
                if tl in hands[s]:
                    hands[s].remove(tl)
                for m in melds[s]:
                    if not m.get("gang") and m.get("tile") == tl:
                        m["gang"] = True
                        break
                else:
                    melds[s].append({"gang": True, "tile": tl})
            elif kind == "an":
                for _ in range(4):
                    if tl in hands[s]:
                        hands[s].remove(tl)
                melds[s].append({"gang": True, "tile": tl})
                for _ in range(4):
                    meld_tiles[s][tl] += 1
            else:
                for _ in range(3):
                    if tl in hands[s]:
                        hands[s].remove(tl)
                melds[s].append({"gang": True, "tile": tl})
                for _ in range(4):
                    meld_tiles[s][tl] += 1
        elif t == "round_ended":
            break
    return out


def decide_metrics(hand, e, g, menzen, tile, river, uid_hand, melds=None):
    """返回 dict；算不动返回 None。

    ⚠ 2026-09-18 修口径：可见张数必须**同时**扣掉四家副露，否则"最优弃牌"
    会在错误的活张数上评选（c135 用完整可见集反而显得更差就是被这个口径坑的）。
    """
    vis = collections.Counter(uid_hand)
    for r in river:
        vis.update(r)
    for m in (melds or []):
        vis.update(m)
    sh_of = {}
    for t in set(hand):
        h2 = list(hand)
        h2.remove(t)
        sh_of[t] = SH(h2, qidui=menzen, exposed_melds=e, gangs=g)
    sh_best = min(sh_of.values())
    sh_act = sh_of[tile]
    uc = {}
    for t, s in sh_of.items():
        if s == sh_best:
            h2 = list(hand)
            h2.remove(t)
            tot, _k = real_ukeire(h2, exposed=e, gangs=g, visible=vis)
            uc[t] = 0 if tot is None else tot
    uke_best = max(uc.values()) if uc else 0
    uke_act = uc.get(tile, 0)
    won_before = False
    try:
        won_before = bool(is_win(list(hand), exposed_melds=e, gangs=g))
    except Exception:
        won_before = False
    best_tiles = [t for t in uc if uc[t] == uke_best] if uc else []
    return {"sh_best": sh_best, "sh_act": sh_act, "bad": sh_act > sh_best,
            "uke_best": uke_best, "uke_act": uke_act,
            "uloss": max(0, uke_best - uke_act) if sh_act == sh_best else 0,
            "opt": (tile in best_tiles), "won_before": won_before, "tile": tile}


def main():
    lim = 0
    for a in sys.argv[1:]:
        if a.isdigit():
            lim = int(a)
    top = board_top(32)
    _dirs = [d for d in (os.environ.get("DEA_DIRS", "server,recent").split(",")) if d]
    _seen = {}
    for _d in _dirs:
        for _f in glob.glob(os.path.join(ROOT, "var", "replays", _d, "*.json")):
            _seen[os.path.basename(_f)] = _f
    files = sorted(_seen.values())
    if lim:
        files = files[-lim:]
    smap = {}
    _ts = {}
    for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("room"):
            smap[r["room"]] = r.get("strategy") or "?"
            _ts[r["room"]] = r.get("ts") or ""
    BD = collections.Counter()
    Ps = collections.defaultdict(collections.Counter)   # 我方按策略
    A = collections.defaultdict(collections.Counter)   # 全量
    B = collections.defaultdict(collections.Counter)   # 排除"弃牌前已可胡"
    Bt = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    Bm = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # [grp][menzen]
    Psm = collections.defaultdict(lambda: collections.defaultdict(collections.Counter)) # [strat][menzen]
    _since = os.environ.get("DEA_SINCE", "")
    if _since:
        files = [f for f in files
                 if _ts.get(os.path.basename(f).split("_r")[0], "") >= _since]
        print("DEA_SINCE=%s => 只保留 %d 个门户文件" % (_since, len(files)))
    done = 0
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        seats = d.get("seats") or []
        if len(seats) != 4:
            continue
        uids = [s.get("user_id") or "" for s in seats]
        strat = smap.get(os.path.basename(f).split("_r")[0], "?")
        for b in d.get("blocks") or []:
            sh = b.get("start_hands")
            if not sh or len(sh) != 4 or any(h is None for h in sh):
                continue
            try:
                rows = audit_round(sh, b.get("events") or [])
            except Exception:
                continue
            done += 1
            for s, hand, e_cnt, g_cnt, tile, river, menzen, cp, pseq, pdrawn, mtiles in rows:
                u = uids[s]
                if not u:
                    continue
                grp = "me" if u == ME else ("top" if u in top else "oth")
                try:
                    m = decide_metrics(hand, e_cnt, g_cnt, menzen, tile, river, hand,
                                       melds=mtiles)
                except Exception:
                    continue
                if m is None:
                    continue
                for C in (A,):
                    c = C[grp]
                    c["n"] += 1
                    c["sh"] += m["sh_best"]
                    c["bad"] += 1 if m["bad"] else 0
                    if not m["bad"]:
                        c["neq"] += 1
                        c["ul"] += m["uloss"]
                        c["ulbad"] += 1 if m["uloss"] > 0 else 0
                bk = m["sh_best"]
                bk = 0 if bk <= 0 else (1 if bk == 1 else (2 if bk == 2 else 3))
                L = Bt[grp][bk]
                L["n"] += 1
                L["sh"] += m["sh_best"]
                L["bad"] += 1 if m["bad"] else 0
                L["opt"] += 1 if m["opt"] else 0
                if not m["bad"]:
                    L["neq"] += 1
                    L["ul"] += m["uloss"]
                if not m["won_before"]:
                    c = B[grp]
                    c["n"] += 1
                    c["sh"] += m["sh_best"]
                    c["bad"] += 1 if m["bad"] else 0
                    if not m["bad"]:
                        c["neq"] += 1
                        c["ul"] += m["uloss"]
                        c["ulbad"] += 1 if m["uloss"] > 0 else 0
                if m["won_before"]:
                    A[grp]["won_before"] += 1
                if m["bad"]:
                    BD[(grp, tile)] += 1
                    BD[(grp, "catch" if cp else "free")] += 1
                for C2, key2 in ((Bm[grp], bool(menzen)), (Psm[strat] if grp == "me" else None, bool(menzen))):
                    if C2 is None:
                        continue
                    c2 = C2[key2]
                    c2["n"] += 1
                    c2["sh"] += m["sh_best"]
                    c2["bad"] += 1 if m["bad"] else 0
                    c2["opt"] += 1 if m["opt"] else 0
                    if not m["bad"]:
                        c2["neq"] += 1
                        c2["ul"] += m["uloss"]
                if grp == "me":
                    q = Ps[strat]
                    q["n"] += 1
                    q["sh"] += m["sh_best"]
                    q["bad"] += 1 if m["bad"] else 0
                    q["opt"] += 1 if m["opt"] else 0
                    if not m["bad"]:
                        q["neq"] += 1
                        q["ul"] += m["uloss"]
    def line(label, c):
        n, ne = c["n"] or 1, c["neq"] or 1
        print("%-10s %8d %8.2f %9d %8.2f%% %10.3f %10.2f %10.2f%%" % (
            label, c["n"], c["sh"] / n, c["bad"], 100.0 * c["bad"] / n,
            c["ul"] / ne, c["ulbad"] / ne * 0 + c["ul"] / ne,
            100.0 * c["ulbad"] / ne))
    for tag, C in (("A 全量", A), ("B 排除'弃牌前已可胡'", B)):
        print("=" * 112)
        print("弃牌牌效逐手对照 [%s]（门户四家重建，%d 局）" % (tag, done))
        print("=" * 112)
        print("%-10s %8s %9s %9s %9s %11s %10s %10s" % (
            "组", "决策", "弃前向听", "打坏", "打坏率", "均进张损失", "进张损失率", ""))
        line("我方", C["me"]); line("top32", C["top"]); line("其他", C["oth"])
        print()
    print("=" * 112)
    print("按弃牌前向听分档：最优弃牌命中率 / 均进张损失")
    print("=" * 112)
    print("%-8s %-8s %8s %10s %11s %11s" % ("组", "向听档", "决策", "最优命中率", "均进张损失", "打坏率"))
    for grp, lab in (("me", "我方"), ("top", "top32"), ("oth", "其他")):
        for bk, bl in ((0, "已听牌"), (1, "一向听"), (2, "二向听"), (3, "三向听+")):
            c = Bt[grp][bk]
            n = c["n"] or 1
            ne = c["neq"] or 1
            print("%-8s %-8s %8d %9.1f%% %11.3f %10.2f%%" % (
                lab, bl, c["n"], 100.0 * c["opt"] / n, c["ul"] / ne,
                100.0 * c["bad"] / n))
        print()
    print("=" * 112)
    print("我方按策略：最优弃牌命中率 / 均进张损失")
    print("=" * 112)
    print("%-16s %8s %9s %11s %12s %10s" % ("策略", "决策", "弃前向听", "最优命中率", "均进张损失", "打坏率"))
    for st, q in sorted(Ps.items(), key=lambda kv: -kv[1]["n"])[:16]:
        n = q["n"] or 1
        ne = q["neq"] or 1
        print("%-16s %8d %9.2f %10.1f%% %12.3f %9.2f%%" % (
            st, q["n"], q["sh"] / n, 100.0 * q["opt"] / n, q["ul"] / ne,
            100.0 * q["bad"] / n))
    print()
    print("=" * 112)
    print("按 门清/副露 分档：最优弃牌命中率 / 均进张损失（'最优命中率'是相对 real_ukeire 口径）")
    print("=" * 112)
    print("%-10s %-8s %8s %11s %11s %9s" % ("组", "副露", "决策", "最优命中率", "均进张损失", "打坏率"))
    for grp, lab in (("me", "我方"), ("top", "top32"), ("oth", "其他")):
        for kk, kl in ((True, "门清"), (False, "有副露")):
            c = Bm[grp][kk]
            nn = c["n"] or 1
            ne = c["neq"] or 1
            print("%-10s %-8s %8d %10.1f%% %11.3f %8.2f%%" % (
                lab, kl, c["n"], 100.0 * c["opt"] / nn, c["ul"] / ne, 100.0 * c["bad"] / nn))
        print()
    print("我方按策略 × 门清/副露：")
    print("%-16s %-8s %8s %11s %11s %9s" % ("策略", "副露", "决策", "最优命中率", "均进张损失", "打坏率"))
    for st in sorted(Psm, key=lambda k: -sum(Psm[k][b]["n"] for b in Psm[k])):
        for kk, kl in ((True, "门清"), (False, "有副露")):
            c = Psm[st][kk]
            if not c["n"]:
                continue
            nn = c["n"] or 1
            ne = c["neq"] or 1
            print("%-16s %-8s %8d %10.1f%% %11.3f %8.2f%%" % (
                st, kl, c["n"], 100.0 * c["opt"] / nn, c["ul"] / ne, 100.0 * c["bad"] / nn))
    print()
    print("打坏明细：", [(k, v) for k, v in BD.most_common(20)])
    print("参考：我方'弃牌前已可胡'点数 = %d / %d（%.2f%%）"
          % (A["me"]["won_before"], A["me"]["n"] or 1,
             100.0 * A["me"]["won_before"] / (A["me"]["n"] or 1)))


if __name__ == "__main__":
    main()
