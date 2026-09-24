# -*- coding: utf-8 -*-
"""`vs_top`：**同房头对头**读尺（本项目最干净的一次对照，2026-09-16 立）。

为什么需要专门一支尺子（STATUS §9.99）：
  · 主判据 `ab_readout` 的"净胜/房"会被**桌强**（β=−0.593）与**池子**污染；
  · 门户口径的机制读数需要补拉 + 只覆盖 ~52%；
  · 而 `var/auto_ranking.jsonl` 里**每房都归档了全房 ranking** ⇒
    凡"我方与强手同房"的房，就是**同一房、同 80 局、同池、同时刻**的天然配对实验，
    用它算出来的差距**无法被"我们运气差/桌弱"解释**。

用法：
    python -X utf8 tools/vs_top.py                 # 用今日榜首 top10 做参照
    python -X utf8 tools/vs_top.py --period all --topn 32
    python -X utf8 tools/vs_top.py --ids u_xxx,u_yyy
"""
from __future__ import annotations

import argparse
import collections
import glob
import io
import json
import os
import ssl
import statistics as st
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"
BASE = "https://10.240.169.190:18080"
RANKING = os.path.join(ROOT, "var", "auto_ranking.jsonl")


def load_rooms(path=RANKING):
    out = []
    for ln in io.open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def pair_rows(rows, me, tops):
    """返回同房配对：(对方 id, 对方分, 对方名次, 我方分, 我方名次, 日期, 房)。

    同一房内可能有多个参照对象（强手之间同房）⇒ 每个都记一条（保持"每房一条"时可用 max 选择）。
    """
    tops = set(tops)
    out = []
    for d in rows:
        if d.get("status") != "finished":
            continue
        rk = d.get("ranking") or []
        by = {x.get("user_id"): x for x in rk}
        if me not in by:
            continue
        for u in rk:
            uid = u.get("user_id")
            if uid not in tops:
                continue
            try:
                out.append((uid, float(u.get("total_score") or 0), int(u.get("rank") or 0),
                            float(by[me].get("total_score") or 0), int(by[me].get("rank") or 0),
                            (d.get("ts") or "")[:10], d.get("room")))
            except Exception:
                continue
    return out


def one_per_room(pairs):
    """同一房命中多个强手时只留**最强的那一个**，保证配对的独立性（每房一条）。"""
    best = {}
    for p in pairs:
        k = p[6] or (p[0], p[5])
        if k not in best or p[1] > best[k][1]:
            best[k] = p
    return list(best.values())


def summary(pairs):
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    d = [p[1] - p[3] for p in pairs]
    sd = st.pstdev(d) if n > 1 else 0.0
    se = sd / n ** 0.5 if n > 1 else 0.0
    return {
        "n": n,
        "top_mean": st.mean([p[1] for p in pairs]),
        "my_mean": st.mean([p[3] for p in pairs]),
        "diff": st.mean(d),
        "sd": sd,
        "se": se,
        "t": (st.mean(d) / se) if se else 0.0,
        "win_rate": sum(1 for x in d if x > 0) / float(n),
        "top_first": sum(1 for p in pairs if p[2] == 1) / float(n),
        "my_first": sum(1 for p in pairs if p[4] == 1) / float(n),
    }


def fetch_top(period="today", topn=10, cookie_file=None):
    ck = io.open(cookie_file or os.path.join(ROOT, "var", ".portal_cookie"),
                 encoding="utf-8-sig").read().strip()
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        "%s/portal/api/leaderboard?period=%s" % (BASE, period),
        headers={"Cookie": ck})
    j = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode("utf-8"))
    return [r["user_id"] for r in (j.get("top") or [])[:topn]], j.get("me") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="today", choices=["today", "week", "all"])
    ap.add_argument("--topn", type=int, default=10)
    ap.add_argument("--ids", default="", help="逗号分隔的 user_id（给了就不查门户）")
    ap.add_argument("--since", default="", help="只看该日期之后的房（YYYY-MM-DD）")
    a = ap.parse_args()
    if a.ids.strip():
        tops, me = [x.strip() for x in a.ids.split(",") if x.strip()], {}
    else:
        tops, me = fetch_top(a.period, a.topn)
        print("阶梯快照（period=%s）：我方 排名 %s / %s 房 / 累计 %s（%+.1f 分/房，1st %s）"
              % (a.period, me.get("rank"), me.get("rooms"), me.get("score"),
                 (me.get("score") or 0) / max(1, me.get("rooms") or 1), me.get("firsts")))
    rows = load_rooms()
    pairs = one_per_room(pair_rows(rows, ME, tops))
    if a.since:
        pairs = [p for p in pairs if p[5] >= a.since]
    s = summary(pairs)
    if not s["n"]:
        print("没有与这 %d 个参照对象同房的记录" % len(tops))
        return 1
    print("同房头对头（%d 房，参照 %d 人）：他们 %+.1f /房 ；我们 %+.1f /房 ⇒ 差 %+.1f（SD %.1f, SE %.1f, t=%+.2f）"
          % (s["n"], len(tops), s["top_mean"], s["my_mean"], s["diff"], s["sd"], s["se"], s["t"]))
    print("  他们分高（赢）%.0f%% ；他们 1st %.0f%% vs 我们 1st %.0f%%"
          % (100 * s["win_rate"], 100 * s["top_first"], 100 * s["my_first"]))
    by = collections.defaultdict(list)
    for p in pairs:
        by[p[0]].append(p)
    print("  逐人：")
    for u, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:12]:
        print("    %-16s n=%2d 他们 %+7.1f 我们 %+7.1f 差 %+7.1f" % (
            u, len(v), st.mean([x[1] for x in v]), st.mean([x[3] for x in v]),
            st.mean([x[1] - x[3] for x in v])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
