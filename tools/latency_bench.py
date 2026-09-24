# -*- coding: utf-8 -*-
"""latency_bench —— 决策延迟基准（**热态**口径，按窗口预算判定）。

为什么必须"热态"：bot 是长驻进程，`shanten`/`_iter_decompositions` 的 lru_cache 在生产里是热的；
冷启动测出来的尾部（首次几百条）不代表稳态。本工具先预热再统计。

判定口径（与 `tools/preflight.py` 一致）：
  - 出牌窗口 `phase=draw`：预算 3000ms（DiscardTimeoutSec=3）
  - 碰/吃/杠响应窗口：预算 1000ms（Peng=Chi=1）
  要求：**超预算条数 = 0**；并打印 p50/p95/p99/max。

用法：
    python -X utf8 tools/latency_bench.py speedc142
    python -X utf8 tools/latency_bench.py speedtugc --files 60 --warm 800 --n 2000
"""
from __future__ import annotations
import argparse, glob, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from offline_replay import to_view, draws, windows      # noqa: E402


def _stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return (0.0,) * 4 + (0, 0)
    p = lambda q: xs[min(n - 1, int(q * (n - 1)))]
    return p(0.5), p(0.95), p(0.99), xs[-1], sum(1 for x in xs if x > 3000), n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy")
    ap.add_argument("--files", type=int, default=60, help="取最近 N 场 dec 记录")
    ap.add_argument("--warm", type=int, default=800, help="预热条数（不计入统计）")
    ap.add_argument("--n", type=int, default=2000, help="统计条数")
    a = ap.parse_args(argv)
    from run_bot import STRATEGY_FACTORIES as F
    if a.strategy not in F:
        raise SystemExit("策略未注册：%s" % a.strategy)
    strat = F[a.strategy]()
    files = sorted(glob.glob(os.path.join(ROOT, "var/replays/auto_*/*.dec.jsonl")))[-a.files:]
    recs = list(draws(files))
    if len(recs) < a.warm + 10:
        raise SystemExit("dec 记录不足：%d" % len(recs))
    for r in recs[:a.warm]:
        strat.decide(to_view(r))
    xs = []
    for r in recs[a.warm:a.warm + a.n]:
        t0 = time.perf_counter()
        strat.decide(to_view(r))
        xs.append((time.perf_counter() - t0) * 1000.0)
    p50, p95, p99, mx, over, n = _stats(xs)
    print("%s 出牌决策 n=%d  p50=%.1fms p95=%.1fms p99=%.1fms max=%.0fms  超3000ms=%d  %s"
          % (a.strategy, n, p50, p95, p99, mx, over, "OK" if over == 0 else "FAIL"))
    try:
        wrec = list(windows(files))
        if wrec:
            for r in wrec[:min(200, len(wrec))]:
                strat.decide(to_view(r))
            ws = []
            for r in wrec[200:2200]:
                t0 = time.perf_counter()
                strat.decide(to_view(r))
                ws.append((time.perf_counter() - t0) * 1000.0)
            w50, w95, w99, wmx, wover, wn = _stats(ws)
            nover = sum(1 for x in ws if x > 1000)
            print("%s 副露窗口 n=%d  p50=%.1fms p95=%.1fms p99=%.1fms max=%.0fms  超1000ms=%d  %s"
                  % (a.strategy, wn, w50, w95, w99, wmx, nover, "OK" if nover == 0 else "FAIL"))
    except Exception as e:
        print("副露窗口基准不可用：", str(e)[:80])
    return 0 if over == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
