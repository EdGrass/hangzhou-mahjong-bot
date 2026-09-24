# -*- coding: utf-8 -*-
"""gang_gap —— 杠（明/补/暗）与杠开的**同房头对头**缺口分解：我方 vs 榜单 top32。

为什么：强场指纹给出 杠开 0.3% vs 1.6%（-1.3pp）。但 杠开 = f(杠频率, 杠后兑现)。
必须先回答是"我们杠得少"还是"杠了不兑现"，否则下一机制会打偏。

口径：
  - 数据 = 门户 var/replays/{server,recent}/*.json（**四家全信息**，blocks[].events 是服务器事件流）；
  - 同一个 game_id 只算一次；同一房里 ME / top32 / 其他 同口径统计；
  - 杠：events 里 type=gang，data.kind ∈ {ming,bu,an}；
  - 杠开：round_ended.data.detail 含 "杠开" 或 "杠飘链"；
  - 杠后胡：该局有人杠，且该局 round_ended 的 winner 就是杠的人。

用法：python -X utf8 tools/gang_gap.py [--top 32] [--dirs server,recent]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def board_top(n):
    try:
        ctx = ssl._create_unverified_context()
        cookie = open(os.path.join(ROOT, "var", ".portal_cookie"),
                      encoding="utf-8-sig").read().strip()
        req = urllib.request.Request(
            "https://10.240.169.190:18080/portal/api/leaderboard?period=all",
            headers={"Cookie": cookie})
        d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                       .read().decode("utf-8"))
        return [(p["rank"], p["user_id"], p["name"]) for p in (d.get("top") or [])][:n]
    except Exception as e:
        print("  (榜单不可达，退化为全部对手口径: %s)" % e)
        return []


def stat_block(block):
    """返回 (gangs_by_seat, winner, detail) —— 纯函数，便于单测。"""
    gangs = collections.defaultdict(list)
    winner, detail, draw = None, [], None
    for e in block.get("events") or []:
        t, s = e.get("type"), e.get("seat")
        if t == "gang" and isinstance(s, int):
            gangs[s].append((e.get("data") or {}).get("kind") or "?")
        elif t == "round_ended":
            d = e.get("data") or {}
            winner = d.get("winner", s)
            detail = [str(x) for x in (d.get("detail") or [])]
            draw = d.get("draw")
    return gangs, winner, detail, draw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=32)
    ap.add_argument("--dirs", default="server,recent")
    a = ap.parse_args()
    board = board_top(a.top)
    rank_of = {u: r for r, u, n in board}
    top_uids = set(rank_of)

    # uid -> Counter
    S = collections.defaultdict(collections.Counter)
    seen_gid = set()
    n_files = 0
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        for p in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                j = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            gid = j.get("game_id") or os.path.basename(p)
            if gid in seen_gid:
                continue
            seats = j.get("seats") or []
            if len(seats) != 4:
                continue
            uids = [s.get("user_id") or "" for s in seats]
            seen_gid.add(gid)
            n_files += 1
            # 累计一局内的杠-胡关系
            for b in j.get("blocks") or []:
                gangs, winner, detail, draw = stat_block(b)
                for i, u in enumerate(uids):
                    if not u:
                        continue
                    S[u]["rounds"] += 1
                    for k in gangs.get(i, ()):
                        S[u]["g_" + k] += 1
                        S[u]["g_all"] += 1
                if draw:
                    continue
                if not isinstance(winner, int) or not (0 <= winner < 4):
                    continue
                wu = uids[winner]
                if not wu:
                    continue
                S[wu]["wins"] += 1
                det = "|".join(detail)
                if "杠开" in det or "杠飘链" in det:
                    S[wu]["w_gang"] += 1
                if "爆头" in det:
                    S[wu]["w_bao"] += 1
                if "财飘" in det:
                    S[wu]["w_piao"] += 1
                for k in gangs.get(winner, ()):
                    S[wu]["g_self_win_" + k] += 1
                if gangs.get(winner):
                    S[wu]["g_any_win"] += 1

    def agg(uids_iter):
        c = collections.Counter()
        for u in uids_iter:
            c.update(S[u])
        return c

    me_c = agg([ME])
    top_c = agg(u for u in top_uids if u != ME)
    oth_c = agg(u for u in S if u != ME and u not in top_uids)

    def pct(x, y):
        return 100.0 * x / y if y else 0.0

    def show(label, c):
        r = c["rounds"] or 1
        w = c["wins"] or 1
        print("%-16s 局 %6d  胡 %6d  杠/轮 %6.3f  明%.3f 补%.3f 暗%.3f  "
              "杠开/胡 %5.2f%%  杠开/轮 %5.2f%%  杠后胡/杠 %5.1f%%  爆头/胡 %5.1f%%"
              % (label, c["rounds"], c["wins"], c["g_all"] / r,
                 c["g_ming"] / r, c["g_bu"] / r, c["g_an"] / r,
                 pct(c["w_gang"], w), pct(c["w_gang"], r),
                 pct(c["g_any_win"], c["g_all"] or 1), pct(c["w_bao"], w)))

    print("=" * 130)
    print("杠 / 杠开 缺口分解（同房头对头，门户四家全信息）  文件 %d" % n_files)
    print("=" * 130)
    show("EdGrass(我方)", me_c)
    if top_uids:
        show("榜单 top%d 合计" % a.top, top_c)
    show("其他对手", oth_c)

    print()
    print("--- 逐 top 玩家（局数 >= 60）---")
    print("%-5s %-20s %6s %6s %8s %8s %8s %9s" %
          ("rank", "name", "局", "胡", "杠/轮", "杠开/胡", "杠后胡%", "爆头/胡"))
    rows = []
    for r, u, n in board:
        c = S[u]
        if c["rounds"] < 60:
            continue
        rows.append((r, n, c))
    for r, n, c in sorted(rows):
        print("%-5d %-20s %6d %6d %8.3f %7.2f%% %7.1f%% %8.1f%%" %
              (r, n[:18], c["rounds"], c["wins"], c["g_all"] / (c["rounds"] or 1),
               pct(c["w_gang"], c["wins"] or 1),
               pct(c["g_any_win"], c["g_all"] or 1),
               pct(c["w_bao"], c["wins"] or 1)))


if __name__ == "__main__":
    main()
