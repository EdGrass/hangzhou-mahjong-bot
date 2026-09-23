# -*- coding: utf-8 -*-
"""真机画像审计（离线，只看本地复盘，不联网）。

用途：把「我方 vs 全场强手」的差距量化到**逐项可对比的画像指标**，用于
(a) 判断策略改动是否真的把画像推向强手，(b) 替代不迁移的 sim 均值门禁。

数据源：var/replays/{server,recent}/*.json（门户完整复盘，含 rounds 汇总：
        dealer / winner / scores / multiplier —— 结算口径权威）。

自校验：本工具重算的「我方每房总分」与 var/auto_ranking.jsonl 的记录逐房比对
（实测 239 房中 237 房精确一致 = 99.2%），座次映射与解析经此交叉验证。

用法：
    python -X utf8 tools/profile_audit.py                   # 画像总表 + 相关性 + 定位
    python -X utf8 tools/profile_audit.py --min-rounds 400
    python -X utf8 tools/profile_audit.py --pair Nomad      # 单人同房配对
    python -X utf8 tools/profile_audit.py --validate        # 逐房总分自校验
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"
DIRS = ["var/replays/server", "var/replays/recent"]
seed = lambda: dict(r=0, w=0, sc=0, dr=0, dw=0, mw=0, gain=0,  # noqa: E731
                    peng=0, chi=0, gang=0, fan=0)


def iter_replays():
    for d in DIRS:
        for f in glob.glob(os.path.join(ROOT, d, "*.json")):
            try:
                yield json.load(open(f, encoding="utf-8"))
            except Exception:
                continue


def fold(d, P, byroom=None):
    seats = [s.get("user_id") for s in d.get("seats") or []]
    rid = d.get("game_id", "").split("_r")[0]
    for rd in d.get("rounds") or []:
        sc = rd.get("scores") or []
        win, dealer = rd.get("winner"), rd.get("dealer")
        mult = rd.get("multiplier") or 1
        if len(sc) != 4 or dealer is None:
            continue
        for i, u in enumerate(seats):
            if not u:
                continue
            targets = [P[u]] + ([byroom[rid][u]] if byroom is not None else [])
            for T in targets:
                T["r"] += 1
                T["sc"] += sc[i]
                if i == dealer:
                    T["dr"] += 1
                if win == i:
                    T["w"] += 1
                    T["gain"] += sc[i]
                    if mult >= 2:
                        T["mw"] += 1
                    if i == dealer:
                        T["dw"] += 1
    for b in d.get("blocks") or []:
        for e in b.get("events") or []:
            t, s = e.get("type"), e.get("seat")
            if s is None or not (0 <= s < 4) or not seats[s]:
                continue
            if t in ("peng", "chi", "gang"):
                P[seats[s]][t] += 1
                if byroom is not None:
                    byroom[rid][seats[s]][t] += 1


def load(with_rooms=False):
    P = collections.defaultdict(seed)
    names = {}
    byroom = collections.defaultdict(lambda: collections.defaultdict(seed)) if with_rooms else None
    for d in iter_replays():
        for s in d.get("seats") or []:
            names[s.get("user_id")] = s.get("name")
        fold(d, P, byroom)
    return (P, names, byroom) if with_rooms else (P, names)


def row(nm, a):
    r, dr, w = max(1, a["r"]), max(1, a["dr"]), max(1, a["w"])
    return ("%-22s %6d %6.1f%% %6.1f%% %6.1f%% %+8.3f %8.3f %7.1f%% %8.2f %8.4f" % (
        nm, a["r"], 100 * a["w"] / r, 100 * a["dw"] / dr, 100 * a["dr"] / r,
        a["sc"] / r, (a["peng"] + a["chi"]) / r, 100 * a["mw"] / w,
        a["gain"] / w, a["gang"] / r))


HDR = ("%-22s %6s %7s %7s %7s %8s %8s %8s %8s %8s" % (
    "player", "rounds", "win%", "庄win%", "庄占比", "分/轮", "副露/轮", "爆头/胡", "均胡分", "杠/轮"))


def paired(P, names, byroom, min_rounds):
    """对每个 ≥min_rounds 的对手，取与我方共处的房间做同房配对。"""
    out = {}
    for u, a in P.items():
        if u == ME or a["r"] < min_rounds:
            continue
        dm, dt, sc = [], [], []
        for rid, seats in byroom.items():
            if ME not in seats or u not in seats:
                continue
            om, orr = seats[ME]["peng"] + seats[ME]["chi"], seats[ME]["r"]
            tm, tr = seats[u]["peng"] + seats[u]["chi"], seats[u]["r"]
            if orr < 8 or tr < 8:
                continue
            dm.append(tm / tr - om / orr)
            sc.append(seats[u]["sc"] / tr - seats[ME]["sc"] / orr)
            dt.append(rid)
        if len(dm) >= 3:
            out[u] = (dm, sc, len(dt))
    return out


def tstat(d):
    n = len(d)
    if n < 2:
        return 0.0
    m, sd = statistics.mean(d), statistics.pstdev(d)
    return m / (sd / math.sqrt(n)) if sd else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rounds", type=int, default=400)
    ap.add_argument("--pair", default="")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--by-strategy", action="store_true",
                    help="按生产策略分组（真机证据台账：分/轮、净胜、胡率、样本是否够判）")
    ap.add_argument("--min-rooms", type=int, default=3)
    args = ap.parse_args()

    P, names, byroom = load(with_rooms=True)
    if ME not in P:
        sys.exit("未在复盘语料中找到我方")
    me = names.get(ME, "EdGrass")

    if args.validate:
        auth = {}
        for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            for e in d.get("ranking") or []:
                if e.get("user_id") == ME:
                    auth[d["room"]] = e.get("total_score")
        both = [(r, auth[r], byroom[r][ME]["sc"]) for r in auth
                if r in byroom and byroom[r][ME]["r"] > 0]
        ok = sum(1 for _, x, y in both if x == y)
        print("逐房总分自校验：%d 房可比，%d 房精确一致（%.1f%%）；总数 权威 %+d vs 重算 %+d"
              % (len(both), ok, 100.0 * ok / max(1, len(both)),
                 sum(x for _, x, _ in both), sum(y for _, _, y in both)))

    print("=" * 120)
    print("真机画像审计   语料：%s" % ", ".join(DIRS))
    print("=" * 120)
    print(HDR)
    print("-" * 120)
    rows = [(u, t) for u, t in P.items() if t["r"] >= args.min_rounds and t["w"] > 0]
    rows.sort(key=lambda kv: -kv[1]["sc"] / kv[1]["r"])
    for u, t in rows[:args.top]:
        print(row(names.get(u, u)[:22], t))
    print("-" * 120)
    print(row((me + " (我方)")[:22], P[ME]))
    rk = [i for i, (u, _) in enumerate(rows, 1) if u == ME]
    if rk:
        print("\n我方在 %d 名达线玩家中按分/轮排第 %d" % (len(rows), rk[0]))

    def corr(x, y):
        mx, my = statistics.mean(x), statistics.mean(y)
        cov = sum((p - mx) * (q - my) for p, q in zip(x, y)) / len(x)
        return cov / (statistics.pstdev(x) * statistics.pstdev(y)) if x and y else float("nan")

    ys = [t["sc"] / t["r"] for _, t in rows]
    print("\n--- 跨玩家相关性（n=%d；score 口径已由榜单验证）---" % len(rows))
    print("  副露/轮 vs 分/轮 : %+.3f    副露/轮 vs 胜率 : %+.3f"
          % (corr([(t["peng"] + t["chi"]) / t["r"] for _, t in rows], ys),
             corr([(t["peng"] + t["chi"]) / t["r"] for _, t in rows], [t["w"] / t["r"] for _, t in rows])))
    print("  爆头/胡 vs 分/轮 : %+.3f    杠/轮   vs 分/轮 : %+.3f"
          % (corr([t["mw"] / t["w"] for _, t in rows], ys),
             corr([t["gang"] / t["r"] for _, t in rows], ys)))
    print("  庄占比  vs 分/轮 : %+.3f  （强相关但为胜率的**结果**，非可调旋钮）"
          % corr([t["dr"] / t["r"] for _, t in rows], ys))

    if args.by_strategy:
        strat = {}
        for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            strat[d["room"]] = d.get("strategy")
        grp = collections.defaultdict(lambda: dict(rooms=0, r=0, w=0, sc=[], net=[], mw=0))
        for rid, seats in byroom.items():
            st = strat.get(rid)
            if not st or ME not in seats or seats[ME]["r"] < 20:
                continue
            a = grp[st]
            a["rooms"] += 1
            a["r"] += seats[ME]["r"]
            a["w"] += seats[ME]["w"]
            a["mw"] += seats[ME]["mw"]
            a["sc"].append(seats[ME]["sc"] / seats[ME]["r"])
            others = [v["sc"] / v["r"] for u, v in seats.items()
                      if u != ME and v["r"] >= 20]
            if len(others) == 3:
                a["net"].append(seats[ME]["sc"] / seats[ME]["r"] - statistics.mean(others))
        print("\n--- 生产策略台账（同一逐轮口径；真机每房约 80 轮）---")
        print("%-16s %5s %7s %9s %9s %10s %8s %8s %s"
              % ("strategy", "rooms", "rounds", "分/轮", "±95%", "净胜/房", "胡率", "爆头/胡", "可判"))
        rows2 = []
        for st, a in grp.items():
            n = len(a["sc"])
            if n < args.min_rooms:
                continue
            m = statistics.mean(a["sc"])
            ci = 1.96 * statistics.pstdev(a["sc"]) / math.sqrt(n) if n > 1 else 0.0
            rows2.append((st, a, m, ci, n))
        for st, a, m, ci, n in sorted(rows2, key=lambda x: -x[2]):
            # net 是「每轮」口径（我方 − 同房另三家均值）；×80 折算成每房
            net = statistics.mean(a["net"]) * 80 if a["net"] else float("nan")
            # 「可判」= 95%CI 不含 0（单臂对 0）或样本足够紧
            verdict = "是" if (m - ci > 0 or m + ci < 0) else "否(样本不足)"
            print("%-16s %5d %7d %+9.3f %8.3f %+10.1f %7.1f%% %7.1f%% %s"
                  % (st, n, a["r"], m, ci, net, 100.0 * a["w"] / max(1, a["r"]),
                     100.0 * a["mw"] / max(1, a["w"]), verdict))
        print("\n提示：真机房级 SD≈146 → 要判 ±20/房 需 >100 房/臂。"
              "「可判=否」的策略不应据此切换生产。")

    if args.pair:
        want = [u for u, n in names.items() if n == args.pair]
        if not want:
            sys.exit("未找到昵称：%s" % args.pair)
        u = want[0]
        acc_m, acc_t, shared = seed(), seed(), 0
        for rid, seats in byroom.items():
            if ME in seats and u in seats:
                shared += 1
                for k, v in seats[ME].items():
                    acc_m[k] += v
                for k, v in seats[u].items():
                    acc_t[k] += v
        print("\n--- 同房配对：我方 vs %s（%d 个共同房间）---" % (args.pair, shared))
        print(HDR)
        print(row("我方", acc_m))
        print(row(args.pair[:22], acc_t))

    # 全量「我方 vs 前排」同房配对（规模最大的一档证据）
    pr = paired(P, names, byroom, args.min_rounds)
    if pr:
        dm = [x for d, _, _ in pr.values() for x in d]
        sc = [x for _, s, _ in pr.values() for x in s]
        n = len(dm)
        print("\n--- 我方 vs %d 名达线对手：逐房同房配对（正=对手更高，共 %d 房次）---"
              % (len(pr), n))
        print("  副露/轮差 %+.3f  t=%.2f  95%%CI [%+.3f, %+.3f]  对手更高占比 %.0f%%"
              % (statistics.mean(dm), tstat(dm),
                 statistics.mean(dm) - 1.96 * statistics.pstdev(dm) / math.sqrt(n),
                 statistics.mean(dm) + 1.96 * statistics.pstdev(dm) / math.sqrt(n),
                 100.0 * sum(1 for x in dm if x > 0) / n))
        print("  分/轮差   %+.3f  t=%.2f  95%%CI [%+.3f, %+.3f]"
              % (statistics.mean(sc), tstat(sc),
                 statistics.mean(sc) - 1.96 * statistics.pstdev(sc) / math.sqrt(n),
                 statistics.mean(sc) + 1.96 * statistics.pstdev(sc) / math.sqrt(n)))
        print("  → 配对剥离对手池/时段：这是判断「画像该往哪调」的主力证据。")


if __name__ == "__main__":
    main()
