# -*- coding: utf-8 -*-
"""`var/_submit_latency_audit.py` —— 真机**提交延迟**与**失效动作**审计（只读，R1182）。

## 为什么

A/B 的效力取决于"我方动作是否及时到达服务端"。本工具从 `logs/auto_*.log` 里抽两类事实：

1. **提交延迟分布**（`sub_ms=`）：p50/p90/p99/max + ≥500ms/≥1s/≥2s 的计数与**时间戳/房号**
   ⇒ 用来回答"慢尖峰是不是跟本机跑重活的时间窗重合"；
2. **失效动作**（`409（已失效）`）：按 action 分类（pass 属正常无操作；**chi/peng/gang/hu/discard 才是真损失**）
   ＋每类的慢样本 ⇒ 用来回答"慢提交到底有没有丢牌"。

用法：
    python -X utf8 var/_submit_latency_audit.py
    python -X utf8 var/_submit_latency_audit.py --since "2026-09-23 20:00:00"
"""
from __future__ import annotations
import argparse, collections, glob, io, os, re, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = re.compile(r"\[(\d\d:\d\d:\d\d)\].*sub_ms=([0-9.]+)")
E409 = re.compile(r"\[(\d\d:\d\d:\d\d)\].*409.*act=(\w+)(?:.*sub_ms=([0-9.]+))?")


def files(since=""):
    """按**文件名里的完整时间戳** `auto_YYYYMMDD_HHMMSS.log` 过滤（R1182 修：早先只比日期+外部时间，会放进同日更早的房）。"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "logs", "auto_*.log"))):
        base = os.path.basename(f)               # auto_20260923_205150.log
        stamp = base[5:20]                       # YYYYMMDD_HHMMSS
        iso = ""
        if len(stamp) == 15 and stamp[8] == "_":
            iso = "%s-%s-%s %s:%s:%s" % (stamp[0:4], stamp[4:6], stamp[6:8],
                                         stamp[9:11], stamp[11:13], stamp[13:15])
        if since and iso and iso < since:
            continue
        out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="只看该日期时间之后的日志（如 2026-09-23 20:00:00）")
    ap.add_argument("--top", type=int, default=8, help="最慢样本打印条数")
    a = ap.parse_args()

    subs, acts = [], collections.defaultdict(list)
    for f in files(a.since):
        name = os.path.basename(f)
        for ln in io.open(f, encoding="utf-8", errors="ignore"):
            m = SUB.search(ln)
            if m:
                subs.append((name, m.group(1), float(m.group(2))))
            m2 = E409.search(ln)
            if m2:
                acts[m2.group(2)].append((name, m2.group(1),
                                          float(m2.group(3)) if m2.group(3) else None))

    print("=" * 84)
    FS = files(a.since)
    print("真机提交延迟 & 失效动作审计（日志 %d 个%s）" % (len(FS),
          ("，since=%s" % a.since) if a.since else ""))
    print("=" * 84)
    vals = [v for _n, _t, v in subs]
    if vals:
        s = sorted(vals)
        q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
        print("提交延迟样本 %d：p50=%.1fms  p90=%.1fms  p99=%.1fms  max=%.1fms"
              % (len(vals), st.median(vals), q(0.90), q(0.99), max(vals)))
        for thr in (500, 1000, 2000):
            hit = [x for x in subs if x[2] >= thr]
            print("  ≥%dms：%d 次（%.1f%%）" % (thr, len(hit), 100.0 * len(hit) / len(vals)))
            for n, t, v in sorted(hit, key=lambda x: -x[2])[:a.top]:
                print("      %s %s  %.1fms" % (n, t, v))
    else:
        print("无 sub_ms 样本")
    print()
    real = ("chi", "peng", "gang", "hu", "discard")
    print("失效动作（409）按 action：")
    for k in ["pass"] + list(real):
        v = acts.get(k) or []
        if not v:
            continue
        slow = [x for x in v if (x[2] or 0) >= 300]
        tag = "（无操作，正常）" if k == "pass" else "（**真损失**）"
        print("  %-8s %5d 次%s  其中 ≥300ms %d 次" % (k, len(v), tag, len(slow)))
        for n, t, ms in sorted([x for x in slow], key=lambda x: -(x[2] or 0))[:3]:
            print("       %s %s %.1fms" % (n, t, ms or 0))
    tot_real = sum(len(acts.get(k) or []) for k in real)
    print("  ⇒ 真损失类合计 %d 次（chi/peng/gang/discard）" % tot_real)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


