# -*- coding: utf-8 -*-
"""被拒副露窗口的**解剖**：门控说"不要"的窗口，形状是什么？哪一种放松是**有原则**的？

动机（STATUS 12:25）：副露缺口 100% 在接受率；学习网络在 1.34x 饱和，而追上 top8 需要 1.43x
⇒ 下一步是"**扩面**"，但扩面必须先知道被拒窗口的形状。

口径：只用我方**真实被问**窗口（dec），且**必须真有合法吃/碰选项**（约占全部记录的 6.3%，
`offline_replay` 的"可索取"同口径）。副露后向听用项目现成函数 `_best_after_claim`
（它内嵌"副露后最优弃牌"，别自己拼 13-3e-g 的账）。
"""
from __future__ import annotations
import collections, glob, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower            # noqa: E402
print("lower ->", lower(idle=True), flush=True)
from offline_replay import to_view, windows
from mahjong.shanten_exact import shanten as SH
from bot.speed import _chi_pairs
from bot.speedtu import _best_after_claim
from bot.ukeire import real_ukeire, visible_counts

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--strategy", default="", help="只看该策略打的房（去掉混合策略的混杂）")
a = ap.parse_args()
paths = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))[-600:]
recs = list(windows(paths, limit_records=40000))
if a.strategy:
    rstrat = {}
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if ln:
            d = json.loads(ln)
            if d.get("room"):
                rstrat[d["room"]] = d.get("strategy")
    recs = [r for r in recs if rstrat.get(str(r.get("g") or "").split("_r")[0]) == a.strategy]
    print("按策略过滤 %s ⇒ 窗口 %d" % (a.strategy, len(recs)))

buck = collections.defaultdict(lambda: [0, 0])
zero_buck = collections.defaultdict(lambda: [0, 0])
skipped = collections.Counter()
for rec in recs:
    v = to_view(rec)
    hand = list(v.get("my_hand") or [])
    offer = v.get("offer_tile")
    melds = v.get("melds") or []
    e = len(melds); g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
    if not offer or len(hand) != 13 - 3 * e - g:
        skipped["len"] += 1; continue
    try:
        before = SH(hand, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
    except Exception:
        skipped["shanten"] += 1; continue
    kind = "peng" if str(v.get("phase")) == "response_peng" else "chi"
    pairs = [None] if kind == "peng" else list(_chi_pairs(hand, offer))
    if kind == "peng" and hand.count(offer) < 2:
        skipped["no_peng"] += 1; continue
    if kind == "chi" and not pairs:
        skipped["no_chi"] += 1; continue
    best = None
    for p in pairs:
        try:
            r = _best_after_claim(hand, e, g, kind, offer, p)
        except Exception:
            continue
        if r and (best is None or r[2] < best):
            best = r[2]
    if best is None:
        skipped["after"] += 1; continue
    act = (rec.get("a") or {}).get("action")
    acc = 1 if act in ("chi", "peng", "gang") else 0
    b = buck[best - before]
    b[0] += 1; b[1] += acc
    # Δ=0 桶再按 **真进张变化** 切开（C136 的判据只接受"进张变好"的那一支）
    if best - before == 0:
        try:
            vis = visible_counts(hand, river=v.get("river"), all_melds=v.get("all_melds"))
            u0 = real_ukeire(hand, exposed=e, gangs=g, visible=vis)[0] or 0
            u1 = None
            for p2 in pairs:
                r2 = _best_after_claim(hand, e, g, kind, offer, p2)
                if not r2:
                    continue
                # 副露后 11 张，取最优弃牌后的 10 张再算进张
                hh = list(hand)
                if kind == "peng":
                    for _ in range(2):
                        hh.remove(offer)
                else:
                    for t in p2:
                        hh.remove(t)
                best_u = None
                for d in sorted(set(hh)):
                    rem = list(hh); rem.remove(d)
                    try:
                        uu = real_ukeire(rem, exposed=e + 1, gangs=g, visible=vis)[0] or 0
                    except Exception:
                        continue
                    if best_u is None or uu > best_u:
                        best_u = uu
                if best_u is not None and (u1 is None or best_u > u1):
                    u1 = best_u
            if u1 is not None:
                k2 = (u1 - u0)
                key = "涨" if k2 > 0 else ("平" if k2 == 0 else "跌")
                z = zero_buck[key]
                z[0] += 1; z[1] += acc
        except Exception:
            pass

print("可分析窗口 %d（跳过 %s）" % (sum(v[0] for v in buck.values()), dict(skipped)))
print("  %-8s %8s %8s %10s" % ("Δ向听", "窗口", "接受", "接受率"))
for k in sorted(buck):
    n, a = buck[k]
    print("  %-8s %8d %8d %9.1f%%%s" % ("%+d" % k, n, a, 100.0 * a / n, "   ← 不亏向听" if k <= 0 else ""))
tot = sum(v[0] for v in buck.values()); acc = sum(v[1] for v in buck.values())
nz = sum(v[0] for k, v in buck.items() if k <= 0); nza = sum(v[1] for k, v in buck.items() if k <= 0)
print("  合计 %d、总体接受率 %.1f%%；「Δ向听<=0」占 %d (%.1f%%)、该组接受率 **%.1f%%**"
      % (tot, 100.0 * acc / max(1, tot), nz, 100.0 * nz / max(1, tot), 100.0 * nza / max(1, nz)))
if zero_buck:
    print()
    print("Δ向听=0 那桶再按「副露后真进张 - 副露前真进张」切开（C136 只该接受「涨」这一支）：")
    print("  %-6s %8s %8s %10s" % ("进张变化", "窗口", "接受", "接受率"))
    for k in ("涨", "平", "跌"):
        n, a = zero_buck[k]
        if n:
            print("  %-6s %8d %8d %9.1f%%" % (k, n, a, 100.0 * a / n))
