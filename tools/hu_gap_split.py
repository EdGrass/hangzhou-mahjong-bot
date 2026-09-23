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
        "<平台地址>/portal/api/leaderboard?period=all",
        headers={"Cookie": cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                   .read().decode("utf-8"))
    return {p["user_id"]: (p["rank"], p["name"]) for p in (d.get("top") or [])[:n]}


def main():
    top = board_top(32)
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "server", "*.json")))
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if lim:
        files = files[-lim:]
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
    print("胡率缺口两段分解（门户 server 四家全信息，文件 %d）" % len(files))
    print("=" * 118)
    print("%-8s %8s %8s %9s %10s %9s %11s %11s %10s" % (
        "组", "席局", "胡率", "听牌率", "未听牌率", "均听巡",
        "听牌局胡率", "未听局胡率", "爆头态率"))
    for g in ("me", "top", "oth"):
        c = S[g]
        n = c["n"] or 1
        tp = c["tp"] or 1
        print("%-8s %8d %7.1f%% %8.1f%% %9.1f%% %10.2f %10.1f%% %10.1f%% %9.1f%%" % (
            {"me": "我方", "top": "top32", "oth": "其他"}[g],
            c["n"], 100.0 * c["hu"] / n, 100.0 * c["tp"] / n,
            100.0 * c["no_tp"] / n, c["tp_draw"] / tp,
            100.0 * c["tp_hu"] / tp, 100.0 * c["no_tp_hu"] / (c["no_tp"] or 1),
            100.0 * c["bao"] / n))
    m, t = S["me"], S["top"]
    dn = lambda a, b: 100.0 * a / (b or 1)
    print()
    print("缺口：胡率 %+.2fpp ；听牌率 %+.2fpp ；听牌后兑现 %+.2fpp（听牌局口径）" % (
        dn(m["hu"], m["n"]) - dn(t["hu"], t["n"]),
        dn(m["tp"], m["n"]) - dn(t["tp"], t["n"]),
        dn(m["tp_hu"], m["tp"]) - dn(t["tp_hu"], t["tp"])))


if __name__ == "__main__":
    main()
