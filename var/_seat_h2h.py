# -*- coding: utf-8 -*-
"""`var/_seat_h2h.py` —— **同房头对头分位分解：我方 vs 同桌另三家**（只读，收缩到本役的房）。

为什么：`_elite_share_by_day.py` 说我们分房表现几乎由对手池决定（强手房 −32~−46，弱房 +52~+78）。
但"为什么会输分"必须落到**同桌四家**上、而且是**当前臂**上，不能用全历史。

口径：只取台账里 `since` 之后的房；同一批房里，把 **我方那个座位** 与 **同桌另三个座位** 对账：
  胡/轮（和牌率）、番/胡（牌的大小）、**分/轮**（真正的目标）、赢分/输分、
  爆头/胡、财飘/胡、杠开/胡、副露/轮、杠/轮（明/补/暗）。
⇒ 同房同对手 ⇒ 对手池差异被消掉，剩下的是**我们自己的牌**。

⚠ 口径（2026-09-24 07:3x 修）：**只用含 `round_ended` 的 block**（本役 6,880/14,383 = 47.8%），分子分母同口径；
无事发 `round_ended` 的 block 既不进分子也不进分母（旧实现只跳分子 ⇒ 比率被摊薄 2.1 倍）。
因此本工具的 **杠/轮** 比 `var/_gang_now.py`（全 block 口径）系统性低 ~11% ⇒ 报杠频率用 `_gang_now`。

用法：
    python -X utf8 var/_seat_h2h.py --since "2026-09-23 03:13:44"
    python -X utf8 var/_seat_h2h.py --since "2026-09-23 03:13:44" --by-arm
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def rooms_since(since, ledger=None):
    out = {}
    ledger = ledger or os.path.join(ROOT, "var", "auto_ranking.jsonl")
    for ln in io.open(ledger, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if (d.get("ts") or "") < since or d.get("status") != "finished":
            continue
        if d.get("room"):
            out[d["room"]] = d.get("strategy") or "?"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--by-arm", action="store_true")
    ap.add_argument("--top", type=int, default=0,
                    help=">0 时按榜单 topN 把对手再拆成 top / 其他（只读门户榜）")
    ap.add_argument("--ledger", default=None, help="台账路径（默认 var/auto_ranking.jsonl；测试用）")
    ap.add_argument("--replays", action="append", default=None,
                    help="复盘的 glob（可重复；默认 var/replays/recent/*.json + var/replays/auto_*/*.json）")
    ap.add_argument("--top-uids", default="",
                    help="逗号分隔的 TOP uid（给了就不读门户榜；测试 / 榜单不可达时用）")
    a = ap.parse_args(argv)
    rooms = rooms_since(a.since, a.ledger)
    if not rooms:
        print("台账里没有 since 之后的房"); return 2

    topu = set()
    if a.top_uids:
        topu = {u.strip() for u in a.top_uids.split(",") if u.strip()}
        if not a.top:
            a.top = 32      # 只是给标签用；实际分层按 --top-uids
    elif a.top:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from gang_gap import board_top
            topu = {u for _r, u, _n in board_top(a.top)}
        except Exception as e:
            print("（榜单不可达，退化为全部对手：%s）" % e)
    S = collections.defaultdict(collections.Counter)
    seen = set()
    pats = a.replays or [os.path.join(ROOT, "var", "replays", "recent", "*.json"),
                         os.path.join(ROOT, "var", "replays", "auto_*", "*.json")]
    pats = [q if os.path.isabs(q) else os.path.join(ROOT, q) for q in pats]
    for pat in pats:
        for p in glob.glob(pat):
            try:
                j = json.load(io.open(p, encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            gid = j.get("game_id") or os.path.basename(p)[:-5]
            room = gid.split("_r")[0]
            if room not in rooms or gid in seen:
                continue
            seats = j.get("seats") or []
            if len(seats) != 4:
                continue
            uids = [s.get("user_id") or "" for s in seats]
            if ME not in uids:
                continue
            seen.add(gid)
            arm = rooms[room]
            my = uids.index(ME)
            for b in j.get("blocks") or []:
                evs = b.get("events") or []
                end = None
                for e in evs:
                    if e.get("type") == "round_ended":
                        end = e
                        break
                if end is None:
                    continue      # 无 round_ended 的 block 既不进分子也不进分母（否则比率被摊薄 ~2.1 倍）
                others = tuple(i for i in range(4) if i != my)
                sides = [("me", (my,)), ("oth", others)]
                if topu:
                    # ★ R1501：**必须同时累积 oth**。旧代码在 --top 时只写 top/other 两个键，
                    #   而每臂「另三家」那行读的是 oth ⇒ **恒为 0**（看着像“对手不赢分”）。
                    #   而 `_pick_arm.py`（10/5 定臂 + §V.66 ②破平）**强制**用 --top 32 ⇒ 10/5 那天必踩。
                    sides = [("me", (my,)),
                             ("top", tuple(i for i in others if uids[i] in topu)),
                             ("other", tuple(i for i in others if uids[i] not in topu)),
                             ("oth", others)]
                for side, idxs in sides:
                    if not idxs:
                        continue
                    c = S[(arm, side)]
                    c["rounds"] += len(idxs)
                d = end.get("data") or {}
                scores = d.get("scores") or []
                fan = d.get("fan")
                det = "|".join(str(x) for x in (d.get("detail") or []))
                w = end.get("seat", d.get("winner"))
                draw = d.get("draw")
                for side, idxs in sides:
                    if not idxs:
                        continue
                    c = S[(arm, side)]
                    for i in idxs:
                        sc = scores[i] if i < len(scores) else 0
                        c["score"] += sc
                        if sc > 0:
                            c["score_win"] += sc
                        elif sc < 0:
                            c["score_loss"] += sc
                        if (not draw) and w == i:
                            c["wins"] += 1
                            if isinstance(fan, (int, float)):
                                c["fan"] += fan
                            for tag in ("爆头", "财飘", "杠开", "杠飘链", "平胡", "豪华七对", "七对"):
                                if tag in det:
                                    c["t_" + tag] += 1
                # 副露/杠：按 seat 记
                for e in evs:
                    t, s = e.get("type"), e.get("seat")
                    if not isinstance(s, int):
                        continue
                    for side, idxs in sides:
                        if not idxs or s not in idxs:
                            continue
                        c = S[(arm, side)]
                        if t in ("peng", "chi"):
                            c["meld"] += 1
                        elif t == "gang":
                            c["g_" + ((e.get("data") or {}).get("kind") or "?")] += 1
                            c["g_all"] += 1

    # 聚合键：把各 arm 相加（本工具只往 (arm, side) 里写；无 --by-arm 时 arm 仍是真实臂名）
    for _side in ("me", "oth", "top", "other"):
        _agg = S[("*", _side)]
        for _k, _v in list(S.items()):
            if _k[0] != "*" and _k[1] == _side:
                for _kk, _vv in _v.items():
                    _agg[_kk] += _vv

    def show(label, c):
        r = c["rounds"] or 1
        w = c["wins"] or 1
        print("%-22s 局 %6d | 胡/轮 %5.2f%% | 番/胡 %.2f | 分/轮 %+7.2f "
              "| 赢 %+7.2f 输 %+7.2f | 爆头/胡 %5.1f%% 财飘 %4.1f%% 杠开 %4.2f%% "
              "| 副露/轮 %.3f 杠/轮 %.3f(明%.3f补%.3f暗%.3f)"
              % (label, c["rounds"], 100.0 * c["wins"] / r, c["fan"] / w, c["score"] / r,
                 c["score_win"] / r, c["score_loss"] / r,
                 100.0 * c["t_爆头"] / w, 100.0 * c["t_财飘"] / w, 100.0 * c["t_杠开"] / w,
                 c["meld"] / r, c["g_all"] / r,
                 c["g_ming"] / r, c["g_bu"] / r, c["g_an"] / r))

    print("同房头对头（本役 %d 房；唯一 gid %d）" % (len(rooms), len(seen)))
    print("=" * 150)
    if a.by_arm:
        for arm in sorted({k[0] for k in S}):
            show("%s 我方" % arm, S[(arm, "me")])
            show("%s 另三家" % arm, S[(arm, "oth")])
            if a.top:
                # ★ R1501：分层也要**按臂**给 —— 否则「哪根臂在 TOP 同桌下更好」根本读不出来
                if S[(arm, "top")]["rounds"]:
                    show("%s vs TOP%s" % (arm, a.top), S[(arm, "top")])
                if S[(arm, "other")]["rounds"]:
                    show("%s vs 非TOP" % arm, S[(arm, "other")])
        print("-" * 150)
    for side, label in (("me", "★ 我方"), ("top", "★ 同桌 TOP%s" % a.top), ("other", "★ 同桌其他")):
        if a.top and side == "top" and not S[("*", "top")]["rounds"]:
            continue
        if a.top and side == "other" and not S[("*", "other")]["rounds"]:
            continue
        if a.top or side == "me":
            show(label, S[("*", side)])
    if not a.top:
        show("★ 同桌另三家", S[("*", "oth")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
