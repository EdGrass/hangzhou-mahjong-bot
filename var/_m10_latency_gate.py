# -*- coding: utf-8 -*-
"""`var/_m10_latency_gate.py` —— **与正式赛同构的 M=10 并发延迟门禁**（只读，低优先级，R1235）。

## 为什么需要（项目自己吃过亏）

`speedsearch` 的教训（`bot/speedsearch.py` 自述）：**"350ms 墙钟预算"在 10 线程共享同一策略实例时，
一次决策实测可达 4.1 秒**——因为线程在等 GIL，预算检查根本没机会执行。
⇒ **只做单线程 latency_bench 不足以证明"能上正式赛"**；正式赛是 **10 桌共用一个策略实例**。

而我们的新臂（BC 154 维网 / 81 维教师排序器 / 副露网）都**增加了 GIL 内的 CPU 工作**，
单线程 p50 只有 12~15ms，**但在 M=10 下没人测过**。

## 做什么

- 载入真实 dec 出牌局面；
- **创建 1 个策略实例**，开 **10 个线程**同时 `decide(view)`（与正式赛同构）；
- 逐次记时（`time.perf_counter`），报 **p50 / p95 / p99 / max** 与 **>1s / >3s 条数**；
- 判定：**>1s 必须为 0**（否则该臂不能在正式赛用）。

用法：
    python -X utf8 var/_m10_latency_gate.py --arms speedvalue,speedvaluebc,speedvaluerank --calls 60
"""
from __future__ import annotations
import argparse, glob, io, json, os, random, statistics as st, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from offline_replay import to_view, draws       # noqa: E402


def load_views(n_files=120, limit=4000):
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
    random.seed(0)
    files = random.sample(files, min(n_files, len(files))) if files else []
    out = []
    for r in draws(files):
        out.append(to_view(r))
        if len(out) >= limit:
            break
    return out


def bench(policy, views, threads=10, calls=60):
    lat = []
    lock = threading.Lock()
    per = max(1, calls)
    chunk = max(1, len(views) // (threads * per) or 1)

    def worker(tid):
        mine = views[tid * chunk:(tid + 1) * chunk] or views[:chunk]
        local = []
        for i in range(per):
            v = mine[i % len(mine)]
            t0 = time.perf_counter()
            try:
                policy.decide(v)
            except Exception:
                pass
            local.append((time.perf_counter() - t0) * 1000.0)
        with lock:
            lat.extend(local)

    ths = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="逗号分隔的臂名")
    ap.add_argument("--calls", type=int, default=60, help="每线程调用次数")
    ap.add_argument("--threads", type=int, default=10, help="并发线程（正式赛同构 = 10）")
    ap.add_argument("--files", type=int, default=120)
    a = ap.parse_args()
    try:
        from _lowprio_run import lower_self
        print("[m10_gate] %s" % lower_self())
    except Exception:
        pass
    views = load_views(a.files)
    if not views:
        print("没有可用局面")
        return 2
    from run_bot import STRATEGY_FACTORIES as F

    print("=" * 96)
    print("M=%d 并发延迟门禁（同构正式赛；每个臂 %d 个实例 × %d 次/线程；局面 %d 个）"
          % (a.threads, 1, a.calls, len(views)))
    print("=" * 96)
    print("%-20s %8s %8s %9s %9s %8s %8s" % ("臂", "p50", "p95", "p99", "max", ">1s", ">3s"))
    bad = []
    for name in [x.strip() for x in a.arms.split(",") if x.strip()]:
        if name not in F:
            print("%-20s  未注册" % name)
            bad.append("%s 未注册" % name)
            continue
        try:
            p = F[name]()
        except Exception as e:
            print("%-20s  实例化失败：%s" % (name, e))
            bad.append("%s 实例化失败" % name)
            continue
        lat = bench(p, views, threads=a.threads, calls=a.calls)
        if not lat:
            print("%-20s  无样本" % name)
            continue
        s = sorted(lat)
        q = lambda p_: s[min(len(s) - 1, int(p_ * len(s)))]
        n1 = sum(1 for x in s if x > 1000.0)
        n3 = sum(1 for x in s if x > 3000.0)
        print("%-20s %7.1fms %7.1fms %8.1fms %8.1fms %8d %8d"
              % (name, st.median(s), q(0.95), q(0.99), max(s), n1, n3))
        if n1:
            bad.append("%s：>1s 共 %d 条（正式赛不可用）" % (name, n1))
    print()
    if bad:
        print("❌ 不通过：")
        for b in bad:
            print("   - " + b)
        return 2
    print("✅ 全部臂在 M=%d 下无 >1s 调用（可上正式赛）" % a.threads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
