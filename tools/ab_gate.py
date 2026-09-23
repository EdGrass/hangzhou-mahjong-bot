"""tools/ab_gate —— L1 门禁的 A/B 统计判定（SpeedE 系同桌面 A/B）。

从 var/arena/history.jsonl 读取 combo 匹配的历史批，输出候选 vs 基准(E)的
场均 delta、95% CI 与裁决。口径对齐 docs/自迭代方案.md §6 与 PROJECT.md §6。

校准（2026-09-06，C001 本地 8 巡实测 587 局）：同桌面单场配对差
σ_d≈33.7/场（逐座每场 σ≈29），远大于旧假设 10 → 按 δ=2/场 判定需
N≈1100+ 局。--sigma 默认 10 仅为向后兼容；实证值优先（per-game 分析见
var/iter/ab_analysis.py 或 docs/iter/reports/C001.md）。

用法：
    python tools/ab_gate.py --combo "speedx1x2+speedEx2" [--delta-min 2.0]
    python tools/ab_gate.py --combo speedx1 --fuzzy          # 模糊列出可比组合
输出含 json 快照；退出码：0=WIN(过晋级线) 1=LOSE 2=DRAW/WEAK 3=无数据。
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def load_batches(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def combo_avg(batches):
    """按 combo 聚合 identities（口径同 arena.runner._write_metrics）。"""
    by_combo = {}
    for b in batches:
        by_combo.setdefault(b.get("combo"), []).append(b)
    res = {}
    for name, bs in by_combo.items():
        n = sum(x.get("games", 0) for x in bs)
        if n == 0:
            continue
        rnd = bs[0].get("rounds", 8)
        ids = {}
        for x in bs:
            for ident in x.get("identities", []):
                e = ids.setdefault(ident["name"], [0.0, 0, 0])
                e[0] += ident["avg_tot"] * x.get("games", 0)
                e[1] += ident["hu_rate"] * x.get("games", 0) * rnd
                e[2] += x.get("games", 0)
        res[name] = {
            "batches": len(bs),
            "games": n,
            "rounds": rnd,
            "identities": sorted(
                ({"name": k, "avg_tot": round(v[0] / v[2], 3),
                  "hu_rate": round(v[1] / v[2] / rnd, 4)}
                 for k, v in ids.items()),
                key=lambda d: d["name"]),
        }
    return res


def judge(combo, combos, delta_min, sigma=10.0):
    """返回 (verdict, dict)。verdict: WIN/LOSE/DRAW/WEAK/NO_DATA。"""
    if combo not in combos:
        return "NO_DATA", {}
    c = combos[combo]
    ids = {i["name"]: i for i in c["identities"]}
    if len(ids) < 2:
        return "NO_DATA", {}
    # 候选 = 非 speedE 的那一方（假定 A/B 组合里基准为 speedE）
    cand = [n for n in ids if n != "speedE"]
    base = [n for n in ids if n == "speedE"]
    if not cand or not base:
        return "NO_DATA", {}
    cname = cand[0]
    d = ids[cname]["avg_tot"] - ids[base[0]]["avg_tot"]
    n = c["games"]
    se = sigma / (n ** 0.5)
    z = 1.96
    ci = (d - z * se, d + z * se)
    if d >= delta_min and ci[0] > 0:
        verdict = "WIN"
    elif ci[1] < 0:
        verdict = "LOSE"
    elif d > 0 and ci[0] <= 0:
        verdict = "DRAW"        # 方向为正但 CI 含 0
    elif d <= 0:
        verdict = "DRAW"
    else:
        verdict = "WEAK"        # CI>0 但幅度不足晋级线
    if d > 0 and ci[0] > 0 and d < delta_min:
        verdict = "WEAK"
    info = {"combo": combo, "candidate": cname, "baseline": "speedE",
            "batches": c["batches"], "games": n, "rounds": c["rounds"],
            "delta": round(d, 3), "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "se": round(se, 4), "sigma": sigma, "delta_min": delta_min,
            "verdict": verdict,
            "cand_avg": ids[cname]["avg_tot"], "base_avg": ids[base[0]]["avg_tot"],
            "cand_hu": ids[cname]["hu_rate"], "base_hu": ids[base[0]]["hu_rate"]}
    return verdict, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--fuzzy", action="store_true",
                    help="模糊模式：列出含 --combo 子串的全部可比组合")
    ap.add_argument("--delta-min", type=float, default=2.0)
    ap.add_argument("--sigma", type=float, default=10.0,
                    help="同桌面单场配对差标准差（实证 σ≈33.7，8巡本地）")
    ap.add_argument("--history", default=os.path.join("var", "arena", "history.jsonl"))
    args = ap.parse_args()

    combos = combo_avg(load_batches(args.history))
    if args.fuzzy:
        for name, c in sorted(combos.items()):
            if args.combo in name and len(c["identities"]) >= 2:
                names = ",".join("%s:%+.1f" % (i["name"], i["avg_tot"])
                                 for i in c["identities"])
                print("%-28s games=%-6d [%s]" % (name, c["games"], names))
        return 0
    verdict, info = judge(args.combo, combos, args.delta_min, args.sigma)
    if verdict == "NO_DATA":
        print("无数据: combo=%s（history=%s；试试 --fuzzy 看现有组合）"
              % (args.combo, args.history))
        return 3
    print("%s  candidate=%s baseline=speedE games=%d batches=%d\n"
          "  delta=%+.3f/场  SE=%.4f  95%%CI=[%+.3f, %+.3f]  (晋级线 delta_min=%+.1f)\n"
          "  胡率  %s=%.2f%%  speedE=%.2f%%\n"
          "  裁决: %s" % (verdict, info["candidate"], info["games"],
                          info["batches"], info["delta"], info["se"],
                          info["ci95"][0], info["ci95"][1], info["delta_min"],
                          info["candidate"], info["cand_hu"] * 100,
                          info["base_hu"] * 100,
                          {"WIN": "WIN → 送 L2 真机同桌",
                           "WEAK": "WEAK → CI 排除 0 但幅度 < δ_min，登记 weak，不上 L2",
                           "DRAW": "DRAW → 与基准统计不可分，登记 dead-end（不上 L2）",
                           "LOSE": "LOSE → 显著劣于基准，登记 dead-end"}[verdict]))
    print(json.dumps(info, ensure_ascii=False))
    return {"WIN": 0, "LOSE": 1, "DRAW": 2, "WEAK": 2}[verdict]


if __name__ == "__main__":
    sys.exit(main())
