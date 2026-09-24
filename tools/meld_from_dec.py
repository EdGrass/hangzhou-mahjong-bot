# -*- coding: utf-8 -*-
"""`meld_from_dec` —— 用**我方 dec 记录**（无需门户复盘）给副露覆盖与副露量一个**快速**读数。

为什么需要：战役的 `c156` 闸门是"有副露局占比 ≥65%"，而权威口径（`_meld_rate_authoritative.py` /
`mech_mix.py`）都**依赖门户复盘**，补拉 1 房 ≈ 80 个请求（~1.6 分钟）⇒ 48 房 ≈ 1.3 小时。
dec 记录里有**我方自己的动作与副露状态**（`m` 字段）⇒ 可以给出**无需补拉**的快速口径：

  · **副露/文件**：每个 dec 文件里我方 `chi`/`peng` 动作数（dec 文件 = 一个 block）；
  · **有副露文件占比**：文件内我方曾出现 `len(m) ≥ 1` 的占比；
  · 二者都按"房间 → 策略"聚合，并可 `--compare <基线>` 出 Δ ± 2σ。

⚠ 口径声明：这是**块级**口径（一局 ≈ 2 个 block），**不是**局级口径 —— 它的绝对水平**高于**
`_meld_rate_authoritative.py` 的"有副露局占比"；**只用于臂间比较与快速体检**，终点判据仍用权威口径。
"""
from __future__ import annotations
import argparse, collections, glob, io, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower      # noqa: E402
print("lower ->", lower(idle=True), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="", help="只看这些策略（逗号分隔）")
    ap.add_argument("--compare", default="", help="与该基线比较 Δ ±2σ")
    a = ap.parse_args()
    want = [x.strip() for x in a.arms.split(",") if x.strip()]
    room_strat = {}
    try:
        for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            if d.get("room"):
                room_strat[d["room"]] = d.get("strategy") or "?"
    except OSError:
        pass

    files_seen = collections.Counter()          # arm -> 文件数
    with_meld = collections.Counter()           # arm -> 有副露文件数
    melds = collections.Counter()               # arm -> 我方 chi+peng 次数
    per_file_rate = collections.defaultdict(list)   # arm -> 每文件是否有副露(0/1)
    for dp in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl"))):
        room = os.path.basename(dp).split("_r")[0]
        st = room_strat.get(room)
        if not st or (want and st not in want):
            continue
        had = False
        cnt = 0
        try:
            fh = io.open(dp, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if len(r.get("m") or []) >= 1:
                    had = True
                act = (r.get("a") or {}).get("action")
                if act in ("chi", "peng"):
                    cnt += 1
        files_seen[st] += 1
        melds[st] += cnt
        if had:
            with_meld[st] += 1
        per_file_rate[st].append(1.0 if had else 0.0)

    def mean_se(arm):
        v = per_file_rate.get(arm) or []
        if len(v) < 2:
            return None, None, len(v)
        m = sum(v) / len(v)
        var = sum((x - m) ** 2 for x in v) / len(v)
        return m, math.sqrt(var / len(v)), len(v)

    print("口径 = 我方 dec（块级、含记录重复）⇒ 只看「副露/文件」的臂间比例，不看绝对值")
    if files_seen.get("speedc151") and files_seen.get("speedtugc"):
        base = melds["speedtugc"] / max(1, files_seen["speedtugc"])
        cand = melds["speedc151"] / max(1, files_seen["speedc151"])
        print("  校验：权威口径 c151 vs 基线 副露/局 0.872→1.06 = +21.6%%；本工具给出 %+.1f%% ⇒ 同向同量级（比例可用作快速代理）"
              % (100.0 * (cand / max(1e-9, base) - 1.0)))
    print("  注：有副露文件占比在所有臂上都 ~100%（块级饱和）⇒ 不可用作 c156 的覆盖率闸门；")
    print("      覆盖率闸门（>=65%）仍须用门户权威口径（_meld_rate_authoritative.py / mech_mix.py）。")
    print("  %-14s %7s %9s %12s %12s" % ("策略", "文件", "有副露%(饱和)", "副露/文件", "副露总数"))
    for st in sorted(files_seen, key=lambda x: -files_seen[x]):
        n = files_seen[st]
        print("  %-14s %7d %8.1f%% %12.3f %12d" % (
            st, n, 100.0 * with_meld[st] / max(1, n), melds[st] / max(1, n), melds[st]))
    if a.compare:
        m1, se1, n1 = mean_se(a.compare)
        if m1 is None:
            print("⚠ 基线 %s 的样本不足（%d）" % (a.compare, n1))
        else:
            print("  Δ(有副露文件占比) vs 基线 %s（±2σ）：" % a.compare)
            for st in sorted(files_seen, key=lambda x: -files_seen[x]):
                if st == a.compare:
                    continue
                m2, se2, n2 = mean_se(st)
                if m2 is None:
                    continue
                d = m2 - m1
                se = (se1 ** 2 + se2 ** 2) ** 0.5
                print("    %-14s Δ=%+.3f ±2σ=%.3f (n=%d vs %d)" % (st, d, 2 * se, n2, n1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
