"""本地模拟器跑分（M2 评估闭环雏形）：策略组合自对弈 → 统计对比。

用法：
    python tools/sim_bench.py --games 200 --rounds 8
输出各组合的平均总分/胡率/流局率/均番 + 局数耗时。
"""
from __future__ import annotations

import argparse
import random
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "..")

from bot.heuristic import HeuristicA            # noqa: E402
from bot.strategy import NaiveStrategy          # noqa: E402
from mahjong.sim import SimGame                 # noqa: E402

COMBO_SPECS = {
    "naive4": lambda: [NaiveStrategy()] * 4,
    "heur4": lambda: [HeuristicA()] * 4,
    "mix2n2h": lambda: [HeuristicA(), HeuristicA(), NaiveStrategy(), NaiveStrategy()],
}


def run_bench(games, rounds, seed0=0, combos=None):
    rng = random.Random(seed0)
    combos = combos or list(COMBO_SPECS)
    rows = []
    for name in combos:
        t0 = time.time()
        agg = {"tot": [0.0] * 4, "hu": [0] * 4, "fan_sum": [0] * 4,
               "draw": 0, "viol": 0, "fallback": 0, "games": 0}
        for g in range(games):
            makers = COMBO_SPECS[name]
            # 每局轮换座位顺序（消除座位偏差）；同一座位的策略身份随轮换平移
            order = list(range(4))
            rng.shuffle(order)
            strategies = [None] * 4
            base_makers = makers()
            for seat in range(4):
                strategies[seat] = base_makers[order[seat]]
            res = SimGame(strategies, rounds=rounds, base=1,
                          seed=seed0 * 10000 + g).run()
            agg["games"] += 1
            for i in range(4):
                agg["tot"][i] += res["totals"][i]
            st = res["stats"]
            for i in range(4):
                agg["hu"][i] += st["hu_count"][i]
                agg["fan_sum"][i] += st["fan_total"][i]
            agg["draw"] += st["draw_count"]
            agg["viol"] += st["violations"]
            agg["fallback"] += st["fallbacks"]
        dt = time.time() - t0
        rounds_total = games * rounds
        hu_all = sum(agg["hu"])
        rows.append({
            "name": name, "games": games, "secs": round(dt, 1),
            "avg_tot": [round(v / games, 2) for v in agg["tot"]],
            "hu_rate": [round(h / rounds_total, 3) for h in agg["hu"]],
            "avg_fan": [round(s / h, 2) if h else 0.0 for s, h in
                        zip(agg["fan_sum"], agg["hu"])],
            "draw_rate": round(agg["draw"] / rounds_total, 3),
            "viol": agg["viol"], "fallback": agg["fallback"],
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rows = run_bench(args.games, args.rounds, args.seed)
    hdr = "%-9s %6s %18s | %12s | %6s %7s %6s %6s" % (
        "组合", "局数", "平均总分(4座)", "胡率(4座)", "均番", "流局率", "违规", "兜底")
    print(hdr)
    for r in rows:
        print("%-9s %6d %18s | %12s | %6s %7.3f %6d %6d" % (
            r["name"], r["games"], r["avg_tot"], r["hu_rate"],
            r["avg_fan"], r["draw_rate"], r["viol"], r["fallback"]))


if __name__ == "__main__":
    main()
