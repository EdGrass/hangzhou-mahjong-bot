# -*- coding: utf-8 -*-
"""弃牌策略离线反事实评估（用**真实牌序**，不用 sim）—— 通用筛子。

思路：dec 记录里每次「摸牌决策」都带 `d` = 我们真实摸到的那张牌。把一局内我方的
**真实后续摸牌序列**取出来，就能对同一个局面做反事实：
    - A 线：按 C130 选的弃牌走，之后用固定续策（_best_discard_t）跟完全相同的牌序；
    - B 线：按 tugc 选的弃牌走，同样跟完。
比较「第几张摸牌胡 / 到听牌」，以及最终是否胡。
这比 sim 强的地方：**牌序是真的**（sim 的牌序是自造的，且无 30 分钟约束、对手池也不对）。
局限：忽略副露（两条线都不吃碰，比较是公平的）、忽略对手行为。
"""
from __future__ import annotations
import collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from run_bot import STRATEGY_FACTORIES as _F   # noqa: E402
from mahjong.hu import is_win               # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402
from bot.speedt import _best_discard_t      # noqa: E402

ME_SEAT_KEY = "s"

def _outcome(tile, hand, exposed, gangs):
    """从 13 张手牌 + 摸到 tile 出发，返回 (done, kind)：0=未成 1=听 2=胡"""
    h = list(hand); h.append(tile)
    try:
        if is_win(h, exposed_melds=exposed, gangs=gangs):
            return True, 2
    except ValueError:
        return True, 0
    try:
        d = _best_discard_t(h, tile, exposed, gangs)
    except Exception:
        d = h[0]
    if d in h:
        h.remove(d)
    try:
        s = exact_shanten(h, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return True, 0
    return False, (1 if s == 0 else 0)

def simulate(first_discard, hand13, draws, exposed, gangs):
    """按固定首弃 + 真实后续牌序推进；返回 (胡时第几张, 首次听牌第几张)。"""
    h = list(hand13)
    if first_discard in h:
        h.remove(first_discard)
    win_at = None; tp_at = None
    for i, t in enumerate(draws, 1):
        done, kind = _outcome(t, h, exposed, gangs)
        if kind == 2 and win_at is None:
            win_at = i
            break
        if kind == 1 and tp_at is None:
            tp_at = i
        if done:
            break
        # 推进：_outcome 内部已弃牌，这里重算一次以拿到新手牌
        hh = list(h); hh.append(t)
        try:
            d = _best_discard_t(hh, t, exposed, gangs)
        except Exception:
            d = hh[0]
        if d in hh:
            hh.remove(d)
        h = hh
    return win_at, tp_at

def collect(n_files, quiet=False):
    """把 dec 语料整理成「决策点」列表：((view, exposed, gangs), 真实后续摸牌)。"""
    files = sorted(glob.glob(os.path.join(ROOT, "var/replays/auto_*", "*.dec.jsonl")))
    files = files[:n_files] if n_files else files
    positions = []
    for dp in files:
        ep = dp.replace(".dec.jsonl", ".jsonl")
        if not os.path.exists(ep):
            continue
        ends = []
        try:
            for ln in open(ep, encoding="utf-8"):
                ln = ln.strip()
                if not ln: continue
                try: e = json.loads(ln)
                except Exception: continue
                if e.get("type") == "round_ended":
                    ends.append(int(e.get("seq") or 0))
        except Exception:
            continue
        if not ends: continue
        ends.sort()
        buckets = collections.defaultdict(list)
        for ln in open(dp, encoding="utf-8"):
            ln = ln.strip()
            if not ln: continue
            try: r = json.loads(ln)
            except Exception: continue
            q = int(r.get("q") or 0); idx = 0
            while idx < len(ends) and ends[idx] < q: idx += 1
            buckets[idx].append(r)
        for _idx, recs in buckets.items():
            draws = [r.get("d") for r in recs if r.get("p") == "draw" and r.get("d")]
            if len(draws) < 3: continue
            di = -1
            for r in recs:
                if r.get("p") != "draw" or not r.get("d"): continue
                di += 1
                if r.get("t") != r.get("s"): continue
                h = list(r.get("h") or []); m = r.get("m") or []
                exposed = len(m)
                gangs = sum(1 for x in m
                            if (x[0] if isinstance(x, list) else x.get("type")) == "gang")
                if not h or len(h) != 14 - 3 * exposed - gangs: continue
                try:
                    if is_win(h, exposed_melds=exposed, gangs=gangs): continue
                except ValueError: continue
                view = {"my_hand": h,
                        "melds": [{"type": x[0], "tile": x[1], "tiles": [x[1]] * 3} for x in m],
                        "drawn_tile": r.get("d"), "god": {}, "all_melds": [], "river": [],
                        "phase": "draw", "seat": r.get("s"), "turn": r.get("t"),
                        "responding_seats": []}
                positions.append(((view, exposed, gangs), list(draws[di + 1:])))
    if not quiet:
        print("语料: %d 文件 / %d 个决策点" % (len(files), len(positions)))
    return positions


def run(positions, base_name, cand_name):
    cand = _F[cand_name]()
    base = _F[base_name]()
    tot = collections.Counter()
    for (view, exposed, gangs), rest in positions:
        try:
            ac = cand.decide(view).get("tile")
            ab = base.decide(view).get("tile")
        except Exception:
            continue
        if not ac or not ab: continue
        tot["positions"] += 1
        if ac == ab:
            tot["same"] += 1
            continue
        tot["differ"] += 1
        wa, ta = simulate(ac, view["my_hand"], list(rest), exposed, gangs)
        wb, tb = simulate(ab, view["my_hand"], list(rest), exposed, gangs)
        if wa is not None: tot["cand_win"] += 1
        if wb is not None: tot["base_win"] += 1
        if ta is not None: tot["cand_tp"] += 1
        if tb is not None: tot["base_tp"] += 1
        if wa is not None and wb is None: tot["win_only_cand"] += 1
        if wb is not None and wa is None: tot["win_only_base"] += 1
        if ta is not None and tb is None: tot["tp_only_cand"] += 1
        if tb is not None and ta is None: tot["tp_only_base"] += 1
    return tot


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    base_name = sys.argv[2] if len(sys.argv) > 2 else "speedtugc"
    cand_name = sys.argv[3] if len(sys.argv) > 3 else "speedc130"
    print("候选=%s  基线=%s" % (cand_name, base_name))
    positions = collect(n)
    tot = run(positions, base_name, cand_name)
    d = max(1, tot["differ"])
    print("可用决策点:", tot["positions"], " 与基线一致:", tot["same"], " **分歧:", tot["differ"], "**")
    print()
    print("在分歧局面上，用**同一真实牌序**推演：")
    print("  候选线：胡 %d (%.1f%%)   到听 %d (%.1f%%)" % (
        tot["cand_win"], 100.0 * tot["cand_win"] / d, tot["cand_tp"], 100.0 * tot["cand_tp"] / d))
    print("  基线线：胡 %d (%.1f%%)   到听 %d (%.1f%%)" % (
        tot["base_win"], 100.0 * tot["base_win"] / d, tot["base_tp"], 100.0 * tot["base_tp"] / d))
    print("  谁先胡: 候选独占 %d  基线独占 %d" % (tot["win_only_cand"], tot["win_only_base"]))
    print("  谁先听: 候选独占 %d  基线独占 %d" % (tot["tp_only_cand"], tot["tp_only_base"]))
    print()
    print("口径：两条线跟同一批真实摸牌、都不吃碰 ⇒ 只测「首弃」的隐藏手速度，")
    print("      只能筛掉连这一步都不占优的候选，不能作最终判定。")
    print("net = (候选独占 - 基线独占) / 分歧 = %+.4f" % (
        (tot["win_only_cand"] - tot["win_only_base"]) / float(d)))


if __name__ == "__main__":
    main()
