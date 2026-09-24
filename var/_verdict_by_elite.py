# -*- coding: utf-8 -*-
"""`var/_verdict_by_elite.py` —— **按"房里有/没有 top32"分层的役次读数**（只读台账，R1218）。

## 为什么

`var/_elite_share_by_day.py` 显示我们的分房表现**几乎由对手池决定**：
带 top32 的房 **−32~−46 分/房**、不带 top32 的房 **+52~+78 分/房**；而我们的房有 **52~82%** 是"强手房"。
⇒ 正式赛（强手密集）里，**决定成败的是"强手房"那一列**。

但 `var/_gate2.py` 的主端点把两类房**混在一起** ⇒ 一个臂可能只是"在弱房更赚"，却在强手房没改善
（或反之）。本工具给出**分层读数**：同一批房里，按"是否有 top32"分别报 分/房 与 第1率。

用法：
    python -X utf8 var/_verdict_by_elite.py --since "2026-09-23 03:13:44" --arms speedc151,speedvalue
"""
from __future__ import annotations
import argparse, collections, io, json, os, ssl, statistics as st, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def board_top(n=32):
    ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request("https://10.240.169.190:18080/portal/api/leaderboard?period=all",
                                 headers={"Cookie": ck})
    j = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode("utf-8"))
    return {r["user_id"] for r in (j.get("top") or [])[:n]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--arms", required=True, help="逗号分隔（如 speedc151,speedvalue）")
    ap.add_argument("--topn", type=int, default=32)
    a = ap.parse_args()
    tops = board_top(a.topn)
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]

    # [arm][slice] = [房数, 分合计, 第1数]
    A = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0, 0]))
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") != "finished" or (d.get("ts") or "") < a.since:
            continue
        arm = d.get("strategy")
        if arm not in arms:
            continue
        rk = d.get("ranking") or []
        me = next((x for x in rk if x.get("user_id") == ME), None)
        if not me:
            continue
        n_elite = sum(1 for x in rk if (x.get("user_id") in tops) and x.get("user_id") != ME)
        sl = "强手房" if n_elite >= 1 else "弱房"
        z = A[arm][sl]
        z[0] += 1
        z[1] += float(me.get("total_score") or 0)
        z[2] += 1 if int(me.get("rank") or 0) == 1 else 0
        if n_elite >= 2:
            # ★ 预登记 §8「决赛相似层（>=2 名 top32）」必报 —— 原实现只产 >=1 层，
            #   而 §8 的判据（< −2×SE合并 ⇒ 按 B2 处理）需要这一层。
            z2 = A[arm]["强手房>=2"]
            z2[0] += 1
            z2[1] += float(me.get("total_score") or 0)
            z2[2] += 1 if int(me.get("rank") or 0) == 1 else 0
        z = A[arm]["全部"]
        z[0] += 1
        z[1] += float(me.get("total_score") or 0)
        z[2] += 1 if int(me.get("rank") or 0) == 1 else 0

    print("=" * 88)
    print("役次读数（按是否有 top%d 分层）：since=%s" % (a.topn, a.since))
    print("=" * 88)
    print("%-14s %-8s %8s %12s %10s" % ("臂", "分层", "房", "分/房", "第1率"))
    for arm in arms:
        for sl in ("全部", "强手房", "弱房", "强手房>=2"):
            z = A[arm][sl]
            if not z or not z[0]:
                continue
            print("%-14s %-8s %8d %12.1f %9.1f%%"
                  % (arm, sl, z[0], z[1] / z[0], 100.0 * z[2] / z[0]))
        print()
    print("注：**强手房那一列才对应正式赛的对手密度**；'全部'列与 `tools/ab_readout.py` 同源但口径更粗。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
