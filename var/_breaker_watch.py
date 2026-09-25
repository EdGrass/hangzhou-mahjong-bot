# -*- coding: utf-8 -*-
"""**熔断预警读出**（只读）：把 `_ab_driver.py` 的熔断判据复刻成"当前离阈值多远"。

为什么（R837）：熔断会在**候选近 k 房差值**低于阈值时**终止 A/B 并回退基线** ⇒
- **快档**：k=6，阈值 **−300**
- **慢档**：k=12，阈值 **−150**
本工具每轮巡检跑一次，让"离被熔断多远"变成可见数字，而不是等驱动打日志。

⚠ 只读复刻，**不替代**驱动自己的判断（若实现细节有差异，以 `_ab_driver.py` 为准）。

用法：python -X utf8 var/_breaker_watch.py            # 用 .ab_mode 的 started
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

import ab_readout as AR          # noqa: E402

def arms_of(cfg):
    """★ R1482：**N 臂支持**（与 `_ab_driver.arms_of` 同口径）。

    旧实现只读 `cfg["a"]/cfg["b"]`；三臂役（`.ab_mode = {"arms":[...]}`）下两臂都是 None
    ⇒ 本工具输出“None vs None / 数据不足”并返回 1 ⇒ `_gate_report.py` 的对应步骤失败。
    """
    if isinstance(cfg.get("arms"), list) and len(cfg["arms"]) >= 2:
        return [str(x) for x in cfg["arms"]]
    return [x for x in (cfg.get("a"), cfg.get("b")) if x]


FAST_K, FAST_THR = 6, -300.0
MILD_K, MILD_THR = 12, -150.0


def recent(strategy, since, k):
    return [r["net"] for r in AR.rooms_for(strategy, since)][-k:]


def _report(a, b, since):
    """单个候选 vs 基线的熔断余量（R1482 从原 main 原样拆出）。"""
    print("熔断预警：%s(候选) vs %s(基线)   since %s" % (b, a, since))
    n_b = len(AR.rooms_for(b, since))
    print("候选臂累计房数 n=%d" % n_b)
    alarm = False
    for k, thr, name in ((FAST_K, FAST_THR, "快档"), (MILD_K, MILD_THR, "慢档")):
        cb = recent(b, since, k)
        ca = recent(a, since, k)
        if len(cb) < k or len(ca) < k:
            print("  %s k=%-2d 阈值%+6.0f ：房数不足（候选 %d / 基线 %d）" % (name, k, thr, len(cb), len(ca)))
            continue
        d = (sum(cb) - sum(ca)) / k
        margin = d - thr
        flag = "★ 会触发" if d < thr else ("⚠ 接近" if margin < 100 else "OK")
        if d < thr:
            alarm = True
        print("  %s k=%-2d 阈值%+6.0f ：当前差值 %+7.1f  余量 %+7.1f  %s" % (name, k, thr, d, margin, flag))
    if alarm:
        print()
        print("★ 按复刻口径本应触发熔断 ⇒ 立刻去 `var/_ab_driver.out` 查是否已打熔断日志；")
        print("  若已触发：记录窗口读数 → 写明『这是兜底触发、不是预登记判决』→ 按先例重启同一战役。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ab-file", default="", help="单测用；默认 var/.ab_mode")
    ap.add_argument("--since", default="",
                    help="★ R1482：窗口起点（`_gate_report.py` 会传；旧版忽略它）")
    a = ap.parse_args()
    p = a.ab_file or os.path.join(ROOT, "var", ".ab_mode")
    m = json.load(io.open(p, encoding="utf-8-sig"))
    since = a.since or m.get("started")
    arms = arms_of(m)
    base = (m.get("bundles") or arms or [m.get("a")])[0]
    cands = [x for x in arms if x and x != base]
    if not base or not cands:
        print("读不到臂集（.ab_mode 缺 arms 也缺 a/b）⇒ 不输出")
        return 1
    for cand in cands:
        _report(base, cand, since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())