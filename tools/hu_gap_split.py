# -*- coding: utf-8 -*-
"""hu_gap_split —— 胡率缺口的两段分解：① 听牌率（速度）② 听牌后兑现（质量/安全）。

为什么：已知同房头对头缺口一半在**胡率**。但胡率 = 听牌率 × 听牌后兑现率，
两段的机制完全不同（前者=副露/牌效，后者=听张宽度/弃牌安全/他家速度）。
不分开就会继续打偏。

口径：门户 server 复盘四家状态机（start_hands + 全事件含各家摸牌），
按 uid 分组（我方 / 榜单 top32 / 其他），只用**同一批房**。
"""
from __future__ import annotations
import collections, glob, json, os, ssl, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from tenpai_race import _rounds, run_round   # noqa: E402
ME = "u_7a3fba48d70b"


def board_top(n=32):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, "var", ".portal_cookie"),
                  encoding="utf-8-sig").read().strip()
    req = urllib.request.Request(
        "https://10.240.169.190:18080/portal/api/leaderboard?period=all",
        headers={"Cookie": cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                   .read().decode("utf-8"))
    return {p["user_id"]: (p["rank"], p["name"]) for p in (d.get("top") or [])[:n]}


def room_index(path=None):
    """room → (strategy, ts) 映射（来自 var/auto_ranking.jsonl）。

    供 `--by-arm`（按臂分组）与 `--since`（只算该时间之后开的房）使用。
    """
    import io as _io
    out = {}
    p = path or os.path.join(ROOT, "var", "auto_ranking.jsonl")
    if not os.path.exists(p):
        return out
    for ln in _io.open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("room"):
            out[d["room"]] = (d.get("strategy") or "?", d.get("ts") or "")
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("limit", nargs="?", type=int, default=0, help="只用最后 N 个文件（0=全部）")
    ap.add_argument("--dir", default="server", choices=["server", "recent"],
                    help="server = 09-14 快照（旧）；recent = 持续补拉的**当前**语料（R1171）")
    ap.add_argument("--by-arm", action="store_true",
                    help="改按**臂**分组（读台账 room→strategy），输出我方在各臂上的机制读数")
    ap.add_argument("--since", default="", help="只算该时间之后开的房（按台账 ts，如 2026-09-23 03:13:44）")
    ap.add_argument("--exclude", default="",
                    help="逗号分隔的子串：文件名含任一即排除（如 `_s2_` 看第1轮）")
    ap.add_argument("--dirs", default="",
                    help="逗号分隔的 glob（相对 var/replays/），如 official_1024_20260924_*；给了它就忽略 --dir")
    a = ap.parse_args()
    top = board_top(32)
    idx = room_index() if (a.by_arm or a.since) else {}
    strat = {k: v[0] for k, v in idx.items()} if a.by_arm else {}
    if a.dirs:
        # R1335: 支持任意目录 glob（如官方赛 official_1024_20260924_*）；不传 --dirs 时行为不变。
        files = []
        for _g in [x.strip() for x in a.dirs.split(",") if x.strip()]:
            # ★ R1403：允许直接给**文件 glob**（如 `4test_rooms/t_*_s2_*.json`）⇒ 能按阶段/批次切片；
            #   给目录名时行为不变（自动补 /*.json）。与 `campaign_scorecard` 同口径。
            _pat = os.path.join(ROOT, "var", "replays", _g)
            if not _pat.lower().endswith(".json"):
                _pat = os.path.join(_pat, "*.json")
            files += glob.glob(_pat)
        files = sorted(set(files))
        if a.exclude:
            _ex = [x.strip() for x in a.exclude.split(",") if x.strip()]
            files = [f for f in files if not any(x in os.path.basename(f) for x in _ex)]
    else:
        files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", a.dir, "*.json")))
    if a.since:
        files = [f for f in files
                 if (idx.get(os.path.basename(f).split("_r")[0], ("", ""))[1] >= a.since)]
    if not files:
        # R1335: 0 文件必须报错（否则下面会输出一堆 +0.00pp，看上去像没有缺口）。
        print("\u274c 没找到复盘文件（%s）⇒ 本工具不给结论" % (a.dirs or a.dir))
        print("   本工具读的是房间快照 .json（如 recent/ 或 fetch_tournament_replays 的 --out 目录）；"
              "官方赛本地录的 *.jsonl 是事件流，请用 tools/official_latency_audit.py 那一类工具。")
        return 2
    if a.limit:
        files = files[-a.limit:]
    S = collections.defaultdict(collections.Counter)
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if len(d.get("seats") or []) != 4:
            continue
        uids = [(s.get("user_id") or "") for s in d["seats"]]
        for rn, dealer, sh, evs in _rounds(d):
            if not sh or len(sh) != 4:
                continue
            try:
                hu, ta, tb, bev = run_round(sh, evs, dealer)
            except Exception:
                continue
            for seat in range(4):
                u = uids[seat]
                if not u:
                    continue
                if a.by_arm:
                    g = (strat.get(os.path.basename(f).split("_r")[0], "?") if u == ME else None)
                    if g is None:
                        continue
                else:
                    g = "me" if u == ME else ("top" if u in top else "oth")
                c = S[g]
                c["n"] += 1
                won = (hu == seat)
                if won:
                    c["hu"] += 1
                tp = ta[seat] is not None
                if tp:
                    c["tp"] += 1
                    c["tp_draw"] += ta[seat]
                    if won:
                        c["tp_hu"] += 1
                else:
                    c["no_tp"] += 1
                    if won:
                        c["no_tp_hu"] += 1
                if bev[seat]:
                    c["bao"] += 1
    print("=" * 118)
    print("胡率缺口两段分解（门户 %s 四家全信息，文件 %d）" % ((a.dirs or a.dir), len(files)))
    print("=" * 118)
    print("%-8s %8s %8s %9s %10s %9s %11s %11s %10s" % (
        "组", "席局", "胡率", "听牌率", "未听牌率", "均听巡",
        "听牌局胡率", "未听局胡率", "爆头态率"))
    label = {"me": "我方", "top": "top32", "oth": "其他"}
    order = ("me", "top", "oth") if not a.by_arm else \
        sorted(S, key=lambda k: -S[k]["n"])
    for g in order:
        if g not in S:
            continue
        c = S[g]
        n = c["n"] or 1
        tp = c["tp"] or 1
        print("%-12s %8d %7.1f%% %8.1f%% %9.1f%% %10.2f %10.1f%% %10.1f%% %9.1f%%" % (
            label.get(g, g),
            c["n"], 100.0 * c["hu"] / n, 100.0 * c["tp"] / n,
            100.0 * c["no_tp"] / n, c["tp_draw"] / tp,
            100.0 * c["tp_hu"] / tp, 100.0 * c["no_tp_hu"] / (c["no_tp"] or 1),
            100.0 * c["bao"] / n))
    if not a.by_arm:
        m, t = S["me"], S["top"]
        dn = lambda a, b: 100.0 * a / (b or 1)
        print()
        print("缺口：胡率 %+.2fpp ；听牌率 %+.2fpp ；听牌后兑现 %+.2fpp（听牌局口径）" % (
            dn(m["hu"], m["n"]) - dn(t["hu"], t["n"]),
            dn(m["tp"], m["n"]) - dn(t["tp"], t["n"]),
            dn(m["tp_hu"], m["tp"]) - dn(t["tp_hu"], t["tp"])))
    else:
        dn = lambda a, b: 100.0 * a / (b or 1)
        print()
        print("（--by-arm：只看①我方席位，按臂分组；请与 --dir server 的 top32 行并排比较）")


if __name__ == "__main__":
    sys.exit(main())
