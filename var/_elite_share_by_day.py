# -*- coding: utf-8 -*-
"""按日：**房里有没有 top32** 的比例，以及两个切片各自的分/房。

若"有强手的房"占比随时间上升 ⇒ "俯冲"主要是**房间组成**变了（对手池里强者密度上升），
而不是我们退化。只读。
"""
from __future__ import annotations


def _lowerself():
    import sys as _s, os as _o
    try:
        _s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))), 'tools'))
        from _lowprio import lower
        lower(idle=True)
    except Exception:
        pass


import collections
import io
import json
import os
import ssl
import statistics
import sys
import urllib.request

_lowerself()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def main():
    ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request("https://10.240.169.190:18080/portal/api/leaderboard?period=all",
                                 headers={"Cookie": ck})
    j = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode("utf-8"))
    tops = set(r["user_id"] for r in (j.get("top") or [])[:32])
    byday = collections.defaultdict(lambda: {"a": [], "b": []})
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") != "finished":
            continue
        rk = d.get("ranking") or []
        me = next((x for x in rk if x.get("user_id") == ME), None)
        if not me or len(rk) != 4:
            continue
        k = "a" if any(x.get("user_id") in tops for x in rk) else "b"
        byday[(d.get("ts") or "")[:10]][k].append((me.get("total_score") or 0, me.get("rank") or 0))
    print("%-12s %5s %7s %9s %8s %9s %8s" % (
        "日期", "房", "强手房%", "强手房/房", "我1st%", "弱房/房", "我1st%"))
    for day in sorted(byday):
        v = byday[day]
        n = len(v["a"]) + len(v["b"])
        if n < 4:
            continue
        a, b = v["a"], v["b"]
        print("%-12s %5d %6.0f%% %9s %7s %9s %7s" % (
            day, n, 100.0 * len(a) / n,
            ("%+.1f" % statistics.mean(x[0] for x in a)) if a else "-",
            ("%.0f%%" % (100.0 * sum(1 for x in a if x[1] == 1) / len(a))) if a else "-",
            ("%+.1f" % statistics.mean(x[0] for x in b)) if b else "-",
            ("%.0f%%" % (100.0 * sum(1 for x in b if x[1] == 1) / len(b))) if b else "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
