# -*- coding: utf-8 -*-
"""ab_mech_verdict —— **一条命令**给出逐臂机制画像 + 与"强者基准"的对比 + A 级判据结论。

背景：月度决策规则 v2（STATUS §9.81）把主路径定为「**机制对齐 + 无害**」：
150 房/臂只能辨 ±33 原始分/房，而我们候选的预期效应是 +5~+15 ⇒ 用分数"证明更好"在一个月内做不到。

本工具输出（门户口径、逐场座位、含逐房得分对账）：
  每臂：房/局/胡率/番·每胡/爆头占胡/副露·每局/**有副露局占比**/拆对率(总体+逐巡)/净胜·每房
  参考：强者基准（§9.64/§9.66，n≈26k 局）
  结论：① 机制是否朝参考移动；② 净胜/房 95% CI 下界是否 ≥ −20 原始分/房（无害）

用法：
  python -X utf8 tools/ab_mech_verdict.py --since "2026-09-16 16:23:34"
"""
from __future__ import annotations
import argparse, collections, glob, io, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"

REF = {"胡率": 28.72, "番/胡": 1.353, "爆头占胡": 26.4, "副露/局": 1.233,
       "有副露局占比": 74.5, "拆对率": 8.4,
       "逐巡拆对": [2.3, 2.5, 4.2, 6.5, 8.6, 10.1, 11.4, 11.8]}


def room_arms():
    out = {}
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        if d.get("room"):
            mine = next((x for x in (d.get("ranking") or []) if x.get("user_id") == ME), None)
            out[d["room"]] = (d.get("strategy") or "?", d.get("ts") or "",
                              float(mine.get("total_score") or 0) if mine else None)
    return out


def scan(since, arms):
    """逐臂统计（门户口径）。"""
    S = collections.defaultdict(lambda: collections.Counter())
    per_room = collections.defaultdict(lambda: collections.defaultdict(list))
    _room_net = collections.defaultdict(lambda: collections.defaultdict(list))
    seen = set()
    files = []
    for d in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*"))):
        files.extend(sorted(glob.glob(os.path.join(d, "*_t0.json"))))
    for f in files:
        bn = os.path.basename(f)
        if ".dec." in bn:
            continue
        room = bn.split("_r")[0]
        info = room_arms().get(room)
        if not info:
            continue
        stg, ts, room_score = info
        if since and ts < since:
            continue
        if arms and stg not in arms:
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        seats = j.get("seats") or []
        ids = [(s.get("user_id") or "") for s in seats]
        if len(ids) != 4 or ME not in ids:
            continue
        gid = j.get("game_id") or bn
        if gid in seen:
            continue
        seen.add(gid)
        me = ids.index(ME)
        rr = j.get("rounds") or []
        # 逐局重建（用于副露/拆对/有副露局）
        cur = None
        gi = 0
        for b in j.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            sh = b.get("start_hands")
            if sh and len(sh) == 4 and any(isinstance(x, (list, tuple)) for x in sh):
                if cur is not None:
                    _finish(S, per_room, stg, cur)
                    gi += 1
                cur = {"hands": [list(x) if isinstance(x, (list, tuple)) else [] for x in sh],
                       "turn": 0, "melds": 0, "melded": False, "pb": [0] * 9, "disc": [0] * 9}
            if cur is None:
                continue
            for e in b.get("events") or []:
                t, s = e.get("type"), e.get("seat")
                if not isinstance(s, int) or not (0 <= s < 4):
                    continue
                if t == "tile_drawn":
                    cur["hands"][s].append(e.get("tile"))
                elif t == "tile_discarded":
                    x = e.get("tile")
                    h = cur["hands"][s]
                    if x in h:
                        if s == me:
                            cur["turn"] += 1
                            if cur["turn"] <= 8:
                                cur["disc"][cur["turn"]] += 1
                                if h.count(x) >= 2:
                                    cur["pb"][cur["turn"]] += 1
                        h.remove(x)
                elif t in ("chi", "peng", "gang"):
                    if s == me:
                        cur["melds"] += 1
                        cur["melded"] = True
                    if t == "chi":
                        used = list((e.get("data") or {}).get("tiles") or [])
                        if e.get("tile") in used:
                            used.remove(e.get("tile"))
                        for y in used:
                            if y in cur["hands"][s]:
                                cur["hands"][s].remove(y)
                    elif t == "peng":
                        for _ in range(2):
                            if e.get("tile") in cur["hands"][s]:
                                cur["hands"][s].remove(e.get("tile"))
                    else:
                        for _ in range(3):
                            if e.get("tile") in cur["hands"][s]:
                                cur["hands"][s].remove(e.get("tile"))
                elif t == "round_ended":
                    if cur is not None:
                        _finish(S, per_room, stg, cur)
                    cur = None
                    gi += 1
        if cur is not None:
            _finish(S, per_room, stg, cur)
        # 结果类端点（胡率/番/爆头/得分）
        details = []
        for b in j.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            for e in b.get("events") or []:
                if e.get("type") == "round_ended":
                    details.append((e.get("data") or {}).get("detail") or [])
        c = S[stg]
        c.setdefault("room_ids", set())
        c["room_ids"].add(room)
        for ri, r in enumerate(rr):
            if not isinstance(r, dict):
                continue
            sc = r.get("scores") or []
            if len(sc) != 4:
                continue
            c["rounds"] += 1
            c["score"] += sc[me]
            _room_net[stg][room].append(sc[me] - sum(sc) / 4.0)
            if r.get("winner") == me:
                c["hu"] += 1
                c["fan"] += r.get("multiplier") or 1
                det = details[ri] if ri < len(details) else []
                if "爆头" in (det or []):
                    c["bo"] += 1
    return S, _room_net


def _finish(S, per_room, stg, cur):
    c = S[stg]
    c["g_rounds"] += 1
    c["melds"] += cur["melds"]
    if cur["melded"]:
        c["melded_rounds"] += 1
    for t in range(1, 9):
        c["disc%d" % t] += cur["disc"][t]
        c["pb%d" % t] += cur["pb"][t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x] if a.arms else None
    if not arms:
        try:
            cfg = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8-sig").read())
            arms = [str(x) for x in (cfg.get("arms") or [cfg.get("a"), cfg.get("b")]) if x]
        except Exception:
            arms = None
    S, per_room = scan(a.since, arms)
    if not S:
        print("窗口内没有已发布的门户复盘（先跑 tools/fetch_room_replays.py）")
        return 1
    print("=" * 118)
    print("机制画像（门户口径，since=%s）。参考 = 强者（§9.64/§9.66，n≈26k 局）" % (a.since or "-"))
    print("=" * 118)
    hdr = ("arm", "房", "局", "胡率", "番/胡", "爆头占胡", "副露/局", "有副露局占比", "拆对率", "净胜/房")
    print("%-13s %4s %5s %7s %7s %8s %8s %12s %7s %9s" % hdr)
    print("%-13s %4s %5s %6.2f%% %7.3f %7.1f%% %8.3f %11.1f%% %6.1f%% %+9.1f" % (
        "【强者参考】", "-", "-", REF["胡率"], REF["番/胡"], REF["爆头占胡"], REF["副露/局"],
        REF["有副露局占比"], REF["拆对率"], float("nan")))
    rows = {}
    for stg in sorted(S):
        c = S[stg]
        n = max(1, c["rounds"])
        hu = 100.0 * c["hu"] / n
        fan = c["fan"] / max(1, c["hu"])
        bo = 100.0 * c["bo"] / max(1, c["hu"])
        meld_p = c["melds"] / max(1, c["g_rounds"])
        melded_share = 100.0 * c["melded_rounds"] / max(1, c["g_rounds"])
        d = sum(c["disc%d" % t] for t in range(1, 9))
        pb = sum(c["pb%d" % t] for t in range(1, 9))
        pb_rate = 100.0 * pb / max(1, d)
        # 逐房原始分 / 净胜：raw_room = Σ(每局我方得分)；net = 4/3 × raw
        raw_rooms = [sum(v) for v in per_room[stg].values() if v]
        raw_mean = st.mean(raw_rooms) if raw_rooms else 0.0
        net_mean = raw_mean * 4.0 / 3.0
        nets = raw_rooms
        print("%-13s %4d %5d %6.2f%% %7.3f %7.1f%% %8.3f %11.1f%% %6.1f%% %+9.1f" % (
            stg, len(c.get("room_ids") or ()), c["rounds"], hu, fan, bo, meld_p, melded_share, pb_rate, net_mean))
        per_turn = [100.0 * c["pb%d" % t] / max(1, c["disc%d" % t]) for t in range(1, 9)]
        print("%-13s   逐巡拆对：%s" % ("", " ".join("%4.1f%%" % x for x in per_turn)))
        rows[stg] = dict(hu=hu, fan=fan, bo=bo, meld_p=meld_p, melded_share=melded_share,
                         pb=pb_rate, raw=raw_mean, per_turn=per_turn, nets=nets,
                         rooms=len(c.get("room_ids") or ()), rounds=c["rounds"])
    print("%-13s   逐巡拆对：%s" % ("【强者参考】", " ".join("%4.1f%%" % x for x in REF["逐巡拆对"])))
    # ★ 尺子校验：逐房"逐局得分之和"必须等于 auto_ranking 的 total_score
    ra = room_arms()
    ok = bad = 0
    for stg in S:
        for room, vals in per_room[stg].items():
            info = ra.get(room)
            if not info or info[2] is None:
                continue
            if abs(sum(vals) - info[2]) <= 0.5:
                ok += 1
            else:
                bad += 1
    if ok or bad:
        print("★ 尺子校验（逐房我方得分之和 vs auto_ranking）：一致 %d / 不一致 %d = %.1f%%"
              % (ok, bad, 100.0 * ok / max(1, ok + bad)))
    # A 级判据
    print("-" * 118)
    print("A 级判据（月度决策规则 v2）：① 机制朝参考移动；② 净胜/房 95% CI 下界 ≥ −20 原始分/房（排除大亏）")
    keys = [("胡率", "hu"), ("番/胡", "fan"), ("爆头占胡", "bo"),
            ("副露/局", "meld_p"), ("有副露局占比", "melded_share")]
    for stg, r in rows.items():
        gaps = [abs(r[k2] - REF[k]) / max(1e-9, abs(REF[k])) for k, k2 in keys]
        mean_abs = st.mean(gaps)
        if r["nets"] and len(r["nets"]) > 1:
            se = st.pstdev(r["nets"]) / math.sqrt(len(r["nets"]))
        else:
            se = float("nan")
        lo_raw = r["raw"] - 1.96 * se if r["nets"] else float("nan")
        print("  %-13s 房=%d 局=%d｜与参考的相对偏差均值 %.3f｜**原始分/房 %+.1f（95%% 下界 %+.1f）**"
              % (stg, r["rooms"], r["rounds"], mean_abs, r["raw"], lo_raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
