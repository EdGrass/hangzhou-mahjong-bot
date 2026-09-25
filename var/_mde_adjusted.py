# -*- coding: utf-8 -*-
"""只读：**强度校正端点能不能救回"判不出来"** —— 比较 净胜/房 与 桌强校正后净胜/房 的 MDE。

背景（R1501）：§V.66 主序列「强手房分/房」池化 SD = 128.9 ⇒ 80 房/臂时 MDE = 40.8 分/房，
而实测臂间差只有 22~38 ⇒ 几乎必然判"不可区分"。若"对手强度"能解释掉一大块方差，
用**校正后**的端点就能把 MDE 压下来（这不改任何预登记阈值，只是给 10/5 定臂多一根更有力的尺子）。

用法：python -X utf8 var/_mde_adjusted.py --since "2026-09-20 00:00:00"
"""
from __future__ import annotations
import argparse, io, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from opp_strength import load_rows, opponent_strength, slope   # noqa: E402
from gang_gap import board_top                                 # noqa: E402

ME = "u_7a3fba48d70b"


def mde(sd, n):
    return 2.0 * sd * math.sqrt(2.0 / n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-20 00:00:00")
    ap.add_argument("--strong-top", type=int, default=32)
    a = ap.parse_args(argv)

    rows = load_rows(os.path.join(ROOT, "var", "auto_ranking.jsonl"))
    opp = opponent_strength(rows)
    top = {u for _r, u, _n in board_top(a.strong_top)}
    recs = []
    for d in rows:
        if d.get("status") != "finished" or (d.get("ts") or "") < a.since:
            continue
        rk = d.get("ranking") or []
        m = next((x for x in rk if x.get("user_id") == ME), None)
        if m is None or len(rk) != 4:
            continue
        o = opp.get(d.get("room"))
        if o is None:
            continue
        oth = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME]
        net = (m.get("total_score") or 0) - sum(oth) / 3.0
        strong = any(x.get("user_id") in top for x in rk if x.get("user_id") != ME)
        recs.append({"ts": d["ts"], "arm": d.get("strategy") or "?", "net": net,
                     "opp": o, "strong": strong, "score": m.get("total_score") or 0})
    if len(recs) < 20:
        print("样本不足：%d" % len(recs)); return 2

    beta = slope([r["opp"] for r in recs], [r["net"] for r in recs])
    print("=" * 100)
    print("窗口 since=%s  房=%d（有因果桌强估计）  β = %+.3f" % (a.since, len(recs), beta))
    print("=" * 100)
    for label, sel in (("全部房", recs), ("强手房", [r for r in recs if r["strong"]])):
        if len(sel) < 10:
            continue
        nets = [r["net"] for r in sel]
        opps = [r["opp"] for r in sel]
        mo = st.mean(opps)
        adj = [r["net"] - beta * (r["opp"] - mo) for r in sel]
        sd_raw, sd_adj = st.stdev(nets), st.stdev(adj)
        so_raw, so_adj = st.stdev([r["score"] for r in sel]), st.stdev(
            [r["score"] - beta * (r["opp"] - mo) for r in sel])
        print("\n[%s] n=%d   桌强 SD=%.1f（均值 %+.1f）" % (label, len(sel), st.stdev(opps), mo))
        print("  净胜/房       SD=%6.1f  ⇒ MDE@80=%5.1f  MDE@120=%5.1f" % (sd_raw, mde(sd_raw, 80), mde(sd_raw, 120)))
        print("  校正后净胜/房 SD=%6.1f  ⇒ MDE@80=%5.1f  MDE@120=%5.1f   （降幅 %.0f%%）"
              % (sd_adj, mde(sd_adj, 80), mde(sd_adj, 120), 100 * (1 - sd_adj / sd_raw)))
        print("  原口径 分/房  SD=%6.1f  ⇒ MDE@80=%5.1f    校正后 %6.1f ⇒ MDE@80=%5.1f"
              % (so_raw, mde(so_raw, 80), so_adj, mde(so_adj, 80)))
        arms = sorted({r["arm"] for r in sel})
        print("  %-24s %5s %10s %12s %10s" % ("臂", "房", "净胜/房", "校正后净胜", "校正SE"))
        per = []
        for arm in arms:
            xs = [r for r in sel if r["arm"] == arm]
            if len(xs) < 10:
                continue
            nn = [r["net"] for r in xs]
            aa = [r["net"] - beta * (r["opp"] - mo) for r in xs]
            se = st.stdev(aa) / math.sqrt(len(aa)) if len(aa) > 1 else float("nan")
            per.append((arm, len(xs), st.mean(nn), st.mean(aa), se))
            print("  %-24s %5d %10.1f %12.1f %10.1f" % (arm, len(xs), st.mean(nn), st.mean(aa), se))
        if len(per) >= 2:
            per.sort(key=lambda t: -t[3])
            (a0, n0, r0, j0, s0), (a1, n1, r1, j1, s1) = per[0], per[1]
            dz = (j0 - j1) / math.sqrt(s0 ** 2 + s1 ** 2)
            print("  前两名（校正后）：%s %.1f vs %s %.1f  Δ=%+.1f  z=%+.2f  ⇒ %s"
                  % (a0, j0, a1, j1, j0 - j1, dz, "可区分" if abs(dz) >= 1.5 else "仍不可区分"))
    return 0


if __name__ == "__main__":
    sys.exit(main())