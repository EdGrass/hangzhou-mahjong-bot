# -*- coding: utf-8 -*-
"""**第一率口径的 A/B 读出**（补 `ab_readout.py` 缺的那一块）。

为什么需要：`ab_readout.py` 印出了每臂的"第一名率/top2率"，但**判决统计量只有净分**
（`b − a = … ± …, t=…`）。而用户的判据是 **"只对比第一率"**，且 journal L4270 记
**"名次分 ≠ 原始分、臂排序也不同"** ⇒ 如果正式赛按名次分/第一率排，我们可能一直在优化错的端点。
本工具把**第一率**也做成"带差值 + z"的判决读出，与净分口径并列。

口径：`rooms_for(strategy, since)` 的房间级 `rank`（与门户 `me.firsts/me.rooms` 同源）。
统计：两比例 z（未配对；本作靠轮转排批保证公平）。
⚠ 房间级噪声极大：40 房时第一率 SE ≈ ±5.5pp ⇒ 只能看方向。

用法：
    python -X utf8 var/_first_rate_readout.py --since "2026-09-20 14:54:07"
    python -X utf8 var/_first_rate_readout.py            # 用 .ab_mode 的 started
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "var"))
try:
    from _lowprio import lower
    lower(idle=True)
except Exception:
    pass

import ab_readout as AR                      # noqa: E402


def arms_of(cfg):
    """★ R1482：**N 臂支持**（与 `_ab_driver.arms_of` 同口径）。

    旧实现只读 `cfg["a"]/cfg["b"]`；三臂役（`.ab_mode = {"arms":[...]}`）下两臂都是 None
    ⇒ 本工具输出“None vs None / 数据不足”并返回 1 ⇒ `_gate_report.py` 的对应步骤失败。
    """
    if isinstance(cfg.get("arms"), list) and len(cfg["arms"]) >= 2:
        return [str(x) for x in cfg["arms"]]
    return [x for x in (cfg.get("a"), cfg.get("b")) if x]


def _mode(path=None):
    p = path or os.path.join(ROOT, "var", ".ab_mode")
    return json.load(io.open(p, encoding="utf-8"))


_AB_FILE = [os.path.join(ROOT, "var", ".ab_mode")]   # R1482：供单测指向临时配置


def _stats(strategy, since):
    ranks = [r["rank"] for r in AR.rooms_for(strategy, since) if r.get("rank")]
    n = len(ranks)
    if not n:
        return None
    f = sum(1 for x in ranks if x == 1)
    t2 = sum(1 for x in ranks if x in (1, 2))
    return {"n": n, "first": f, "first_pct": 100.0 * f / n,
            "top2": t2, "top2_pct": 100.0 * t2 / n,
            "mean_rank": sum(ranks) / n}


def _z(p1, n1, p2, n2):
    """两比例 z（p1-p2）。"""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 0.0, 0.0
    pp = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = (pp * (1 - pp) * (1.0 / n1 + 1.0 / n2)) ** 0.5
    d = p1 - p2
    return d, se, (d / se if se > 0 else 0.0)


def _report(sa, sb, since):
    """单个候选 vs 基线的第一率读数（R1482 从原 main 原样拆出）。"""
    print("第一率口径：%s（基线） vs %s（候选）   since %s" % (sa, sb, since or "(全时段)"))
    print("  （以下 b = 候选 %s，a = 基线 %s）" % (sb, sa))
    A = _stats(sa, since)
    B = _stats(sb, since)
    if not A or not B:
        print("数据不足：A=%s B=%s" % (A, B))
        return 1
    print("%-14s %6s %10s %10s %10s" % ("臂", "房数", "第一名率", "top2率", "均名次"))
    for nm, s in ((sa, A), (sb, B)):
        print("%-14s %6d %9.1f%% %9.1f%% %10.2f" % (
            nm, s["n"], s["first_pct"], s["top2_pct"], s["mean_rank"]))
    d, se, z = _z(B["first_pct"] / 100.0, B["n"], A["first_pct"] / 100.0, A["n"])
    print()
    print("★ 第一率  b − a = %+.1fpp  SE=%.1fpp  z=%+.2f" % (100 * d, 100 * se, z))
    d2, se2, z2 = _z(B["top2_pct"] / 100.0, B["n"], A["top2_pct"] / 100.0, A["n"])
    print("  top2率  b − a = %+.1fpp  SE=%.1fpp  z=%+.2f" % (100 * d2, 100 * se2, z2))
    print("  均名次  b − a = %+.2f" % (B["mean_rank"] - A["mean_rank"]))
    print()
    print("⚠ 房间级噪声极大（SE 见上）⇒ 只能看方向；判决仍以预登记端点为准。")
    print("⚠ 记号约定：本工具与 `ab_readout` 一致——SE 一律明写；需要 CI 时自行乘 1.96。")
    # ★ 对手强度校正（与 `ab_readout` 的净分端点同等严谨）
    try:
        from opp_strength import load_rows, opponent_strength, slope
        _rows = load_rows(os.path.join(ROOT, "var", "auto_ranking.jsonl"))
        _ostr = opponent_strength(_rows)
    except Exception as _e:
        _ostr = {}
        print("  (对手强度不可用: %s)" % _e)
    if _ostr:
        def _pair(strategy):
            out = []
            for r in AR.rooms_for(strategy, since):
                o = _ostr.get(r.get("room"))
                if o is None or not r.get("rank"):
                    continue
                out.append((o, 1.0 if r["rank"] == 1 else 0.0))
            return out
        PA = _pair(sa); PB = _pair(sb)
        if len(PA) >= 10 and len(PB) >= 10:
            xs = [o for o, _ in (PA + PB)]
            ys = [y for _, y in (PA + PB)]
            beta = slope(xs, ys)
            oa = sum(o for o, _ in PA) / len(PA)
            ob = sum(o for o, _ in PB) / len(PB)
            pa = sum(y for _, y in PA) / len(PA)
            pb = sum(y for _, y in PB) / len(PB)
            adj_b = pb - beta * (ob - oa)
            print()
            print("★ 对手强度校正（因果口径：只用该房之前的历史）")
            print("  对手强度/房：A=%+.1f  B=%+.1f  差(B−A)=%+.1f   β_第一率=%+.5f/分" % (oa, ob, ob - oa, beta))
            print("  未调整第一率  b − a = %+.1fpp" % (100 * (pb - pa)))
            print("  调整后第一率  b − a = %+.1fpp   （两臂拉到共同桌强）" % (100 * (adj_b - pa)))
        else:
            print()
            print("  (对手强度可用房数不足：A=%d B=%d)" % (len(PA), len(PB)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--ab-file", default="", help="单测用；默认 var/.ab_mode")
    a = ap.parse_args()
    m = _mode(a.ab_file or None)
    since = a.since or m.get("started")
    arms = arms_of(m)
    base = (m.get("bundles") or arms or [m.get("a")])[0]
    cands = [x for x in arms if x and x != base]
    if not base or not cands:
        print("读不到臂集（.ab_mode 缺 arms 也缺 a/b）⇒ 不输出")
        return 1
    print("A/B 第一率口径：基线 %s；候选 %s   since %s"
          % (base, ", ".join(str(c) for c in cands), since or "(全时段)"))
    rc = 0
    for cand in cands:
        rc |= _report(base, cand, since)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())