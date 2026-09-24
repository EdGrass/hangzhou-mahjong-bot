# -*- coding: utf-8 -*-
"""`var/_gang_now.py` —— **本役（当前臂）的杠频率：我方 vs 同房另三家**（只读）。

为什么：`tools/gang_gap.py` 的历史口径（179,126 局，跨多个策略世代）显示我们 杠/轮 **0.010** vs top32 **0.028**。
但那个口径混了"没有自杠路径的旧世代"。本工具把口径**收缩到本役的房**（台账里 `since` 之后的房），
同一批房里我方 vs 另三家，回答"**现在的臂还在不在杠得少**"。

用法：
    python -X utf8 var/_gang_now.py --since "2026-09-23 03:13:44"
    python -X utf8 var/_gang_now.py --since "2026-09-23 03:13:44" --by-arm
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from gang_gap import ME, stat_block          # noqa: E402


def rooms_since(since):
    """台账 → {room: strategy}（本役的房）。"""
    out = {}
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if (d.get("ts") or "") < since:
            continue
        if d.get("status") != "finished":
            continue
        r = d.get("room")
        if r:
            out[r] = d.get("strategy") or "?"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--by-arm", action="store_true")
    a = ap.parse_args(argv)
    rooms = rooms_since(a.since)
    print("本役房数（台账）%d" % len(rooms))
    if not rooms:
        return 2

    pats = [os.path.join(ROOT, "var", "replays", "recent", "*.json"),
            os.path.join(ROOT, "var", "replays", "auto_*", "*.json")]
    seen = set()
    S = collections.defaultdict(collections.Counter)      # (arm, side) -> Counter
    n_used = 0
    for pat in pats:
        for p in glob.glob(pat):
            try:
                j = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            gid = j.get("game_id") or os.path.basename(p)[:-5]
            key = gid.split("_r")[0]
            if key not in rooms or gid in seen:
                continue
            seats = j.get("seats") or []
            if len(seats) != 4:
                continue
            uids = [s.get("user_id") or "" for s in seats]
            if ME not in uids:
                continue
            seen.add(gid)
            n_used += 1
            arm = rooms[key]
            my = uids.index(ME)
            for b in j.get("blocks") or []:
                gangs, winner, detail, draw = stat_block(b)
                for side, idxs in (("me", [my]), ("oth", [i for i in range(4) if i != my])):
                    for i in idxs:
                        c = S[(arm if a.by_arm else "*", side)]
                        c["rounds"] += 1
                        for k in gangs.get(i, ()):
                            c["g_" + k] += 1
                            c["g_all"] += 1
                        if (not draw) and winner == i:
                            c["wins"] += 1
                            det = "|".join(detail or [])
                            if "杠开" in det or "杠飘链" in det:
                                c["w_gang"] += 1
    print("用到的我方局（唯一 gid）%d" % n_used)
    if not n_used:
        return 2

    # 聚合键：把各 arm 相加（本工具只往 (arm, side) 里写；无 --by-arm 时 arm 仍是真实臂名）
    for _side in ("me", "oth"):
        _agg = S[("*", _side)]
        for _k, _v in list(S.items()):
            if _k[0] != "*" and _k[1] == _side:
                for _kk, _vv in _v.items():
                    _agg[_kk] += _vv

    def show(label, c):
        r = c["rounds"] or 1
        w = c["wins"] or 1
        print("%-26s 局 %6d 胡 %5d | 杠/轮 %.3f  明%.3f 补%.3f 暗%.3f | 杠开/胡 %.2f%%"
              % (label, c["rounds"], c["wins"], c["g_all"] / r,
                 c["g_ming"] / r, c["g_bu"] / r, c["g_an"] / r,
                 100.0 * c["w_gang"] / w))

    print("=" * 110)
    if a.by_arm:
        arms = sorted({k[0] for k in S})
        for arm in arms:
            show("%s 我方" % arm, S[(arm, "me")])
            show("%s 另三家" % arm, S[(arm, "oth")])
    show("★ 本役 我方", S[("*", "me")])
    show("★ 本役 另三家（同房）", S[("*", "oth")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
