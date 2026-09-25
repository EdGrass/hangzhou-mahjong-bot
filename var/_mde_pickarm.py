# -*- coding: utf-8 -*-
"""只读：§V.66 **主序列（强手房分/房）的 MDE 估算** —— “这根尺子到底量得出多大的差”。

**为什么查这个**：10/5 选臂和役4/役5 判词都压在 `var/_pick_arm.py` 的主序列上，规则是
**|Δ| < 2×SE ⇒ 不可区分**（不可区分就退到两半 Pareto 破平）。所以真正决定“10/7 装哪根臂”的，
可能不是“哪根更强”，而是“这根尺子在役盒大小的样本下量得出多大的差”。

**它算什么**：复用 `_pick_arm.py` 完全相同的载入与强手房定义（`tools.gang_gap.board_top(32)`），
输出 ① 各臂强手房分/房的 SD；② n_strong ∈ {30,40,60,80,120} 时的 2×SE（合并口径 = MDE）；
③ 与历史实测 Δ 对照。**只读台账，不动任何生产文件。**

用法：python -X utf8 var/_mde_pickarm.py --since "2026-09-20"
"""
from __future__ import annotations
import argparse, collections, io, json, math, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-20")
    ap.add_argument("--me", default=ME)
    ap.add_argument("--strong-top", type=int, default=32)
    a = ap.parse_args(argv)

    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        from gang_gap import board_top
        top = {u for _r, u, _n in board_top(a.strong_top)}
    except Exception as e:
        print("榜单不可达 ⇒ 不给结论:", type(e).__name__, e); return 2
    if not top:
        print("榜单为空 ⇒ 不给结论"); return 2

    by = collections.defaultdict(lambda: {"all": [], "strong": [], "first": 0})
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") != "finished" or (d.get("ts") or "") < a.since:
            continue
        rk = d.get("ranking") or []
        mine = [x for x in rk if x.get("user_id") == a.me]
        if not mine:
            continue
        strong = any(u in top for u in (x.get("user_id") for x in rk) if u != a.me)
        c = by[d.get("strategy") or "?"]
        sc = float(mine[0].get("total_score") or 0)
        c["all"].append(sc)
        if strong:
            c["strong"].append(sc)
        if int(mine[0].get("rank") or 0) == 1:
            c["first"] += 1

    print("=" * 108)
    print("§V.66 主序列：强手房分/房 —— 各臂分布（since=%s，榜单 TOP%d，n_all≥20 才列）" % (a.since, a.strong_top))
    print("=" * 108)
    print("%-22s %6s %7s %10s %8s %8s %8s" % ("臂", "房", "强手房", "强手均值", "SD_强手", "SD_全部", "第1率"))
    rows = []
    for arm, c in sorted(by.items(), key=lambda kv: -len(kv[1]["all"])):
        n, ns = len(c["all"]), len(c["strong"])
        if n < 20:
            continue
        sd_s = statistics.stdev(c["strong"]) if ns >= 2 else float("nan")
        sd_a = statistics.stdev(c["all"]) if n >= 2 else float("nan")
        mean_s = statistics.mean(c["strong"]) if ns else float("nan")
        rows.append((arm, n, ns, mean_s, sd_s, sd_a))
        print("%-22s %6d %7d %10.1f %8.1f %8.1f %7.1f%%" % (arm, n, ns, mean_s, sd_s, sd_a, 100.0 * c["first"] / n))

    # 合并 SD（按强手房数加权）—— MDE 用一个保守的“池化 SD”，不按臂各自挑最好的
    num = den = 0.0
    for _arm, _n, ns, _m, sd_s, _sd_a in rows:
        if ns >= 2 and sd_s == sd_s:
            num += (ns - 1) * sd_s * sd_s
            den += (ns - 1)
    sd_pool = math.sqrt(num / den) if den else float("nan")
    print()
    print("合并（池化）SD_强手 = %.1f 分/房" % sd_pool)
    print()
    print("=" * 108)
    print("MDE：两臂各 n_strong 房、|Δ| ≥ 2×SE 才判“可区分”（SE_pooled = SD×√(2/n)）")
    print("=" * 108)
    print("%12s %12s   %s" % ("n_strong/臂", "MDE(分/房)", "含义"))
    for ns in (30, 40, 60, 80, 100, 120, 160):
        se = sd_pool * math.sqrt(2.0 / ns)
        mde = 2 * se
        tag = ""
        if ns == 30:
            tag = "§V.66 最低房数门槛（只有比这更大的差才判得出）"
        elif ns == 80:
            tag = "全到盒 80/臂（判词线）"
        elif ns == 120:
            tag = "役盒 120/臂"
        print("%12d %12.1f   %s" % (ns, mde, tag))

    print()
    print("对照：本窗口内实测臂间差（强手房分/房）")
    base = [r for r in rows if r[2] >= 20]
    for i in range(len(base)):
        for j in range(i + 1, len(base)):
            a0, a1 = base[i], base[j]
            d = a1[3] - a0[3]
            se = math.sqrt((a0[4] ** 2 / a0[2]) + (a1[4] ** 2 / a1[2])) if (a0[2] and a1[2]) else float("nan")
            print("  %-22s vs %-22s Δ=%+8.1f   2×SE=%6.1f  ⇒ %s"
                  % (a0[0], a1[0], d, 2 * se, "可区分" if abs(d) >= 2 * se else "**不可区分**"))
    return 0


if __name__ == "__main__":
    sys.exit(main())