"""tools/stability —— SpeedA 变体稳定性矩阵（一键回归）。

对每个策略跑 N seeds × rounds 局，断言：
  0 违规 / 0 兜底异常 / 总分守恒 / 局数完整
并输出 胡率/流局率 参考。退出码 0=全过。

用法：
    python tools/stability.py [--rounds 8] [--seeds 4] [--strategy speedA]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "..")

from arena.runner import STRATEGIES            # noqa: E402
from mahjong.sim import SimGame               # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--strategy", default="", help="单策略跑（默认全部）")
    args = ap.parse_args()

    names = [args.strategy] if args.strategy else list(STRATEGIES)
    ok = True
    for name in names:
        hu = dr = vi = fb = 0
        cons = True
        t0 = time.time()
        for s in range(args.seeds):
            r = SimGame([STRATEGIES[name]()] * 4,
                        rounds=args.rounds, seed=args.seed0 + s).run()
            st = r["stats"]
            hu += sum(st["hu_count"])
            dr += st["draw_count"]
            vi += st["violations"]
            fb += st["fallbacks"]
            cons = cons and (sum(r["totals"]) == 0)
        tot = 4 * args.seeds * args.rounds
        good = cons and vi == 0
        ok = ok and good
        print("%-10s 违规=%-5d 兜底=%-5d 守恒=%-5s 胡率=%5.1f%% "
              "流局=%5.1f%% (%.0fs) %s" % (
                  name, vi, fb, cons, hu / tot * 100, dr / tot * 100,
                  time.time() - t0, "PASS" if good else "FAIL"), flush=True)
    print("稳定性矩阵:", "ALL PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
