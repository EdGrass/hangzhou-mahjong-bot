# -*- coding: utf-8 -*-
"""ab_tenpai —— 逐臂的**听牌速度端点**（门户口径、逐场座位、零重算假设）。

为什么需要（§4c-62/63 + §0★.4）：
- 我方与同池强玩家（rank 11）**最大的差值不是分数，是听牌速度**：第 8 巡 45.8% vs 55.3%（−9.5pp）；
- 而"分/房"这个判据在 150 房/臂下只能判 ±33 分/房 ⇒ 小效应测不出来；
- 听牌率是**逐局事件**：p≈0.45、80 局/房 ⇒ 每房 SE≈5.6pp ⇒ **30 房/臂就能辨 ~3pp**（同样的钱买到 ~10 倍功效）。
  ⚠ 它不是判据（本项目已 9 次证明行为画像 ↔ 得分不可迁移），它的用途是**筛掉"干预没生效"的臂**、
  以及**在候选之间排优先级**（哪条路线真的把听牌速度提上去了）。

口径：`rounds[].scores` 的逐房求和必须等于 `auto_ranking.jsonl` 的 `total_score`（内置校验），
座位取**每个文件自己的 `seats`**（本房 10 场逐场重洗，见 §9.56）。

用法：python -X utf8 tools/ab_tenpai.py [--since "..."] [--arms a,b]
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as ex_shanten          # noqa: E402

ME = "u_7a3fba48d70b"
MAXTURN = 8


def room_arms():
    out, conflicts = {}, []
    raw = collections.defaultdict(list)
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("room"):
            raw[d["room"]].append(d)
    for room, ds in raw.items():
        fin = [x for x in ds if x.get("status") == "finished"] or ds
        pick = fin[-1]
        out[room] = (pick.get("strategy") or "?", pick.get("ts") or "", pick)
        if len({(x.get("strategy") or "?") for x in ds}) > 1:
            conflicts.append(room)
    return out, conflicts


def rounds_of(j):
    """blocks → 逐局 {hands, nm, ng, turn, events}（与 tools/dealer_split.py 同口径）。"""
    out, cur = [], None
    for b in j.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        sh = b.get("start_hands")
        if sh and len(sh) == 4 and any(isinstance(x, (list, tuple)) for x in sh):
            if cur is not None:
                out.append(cur)
            cur = {"hands": [list(x) if isinstance(x, (list, tuple)) else [] for x in sh],
                   "nm": [0] * 4, "ng": [0] * 4, "turn": [0] * 4, "events": []}
        if cur is not None:
            cur["events"].extend(b.get("events") or [])
    if cur is not None:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--arms", default="")
    ap.add_argument("--maxturn", type=int, default=MAXTURN)
    ap.add_argument("--lowprio", action="store_true", help="实盘期间用：把本进程降到 Idle 优先级")
    a = ap.parse_args()
    if a.lowprio:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from _lowprio import lower
            lower(idle=True)
        except Exception:
            pass
    arms_filter = [x for x in a.arms.split(",") if x] if a.arms else None

    rmap, conflicts = room_arms()
    S = collections.defaultdict(lambda: [0] * 8)   # 局, tp4, tp6, tp8, melds, wins, fan_sum, rooms
    room_sum = collections.defaultdict(float)      # ★ 尺子校验用：逐房我方得分累加
    per_room = collections.defaultdict(lambda: collections.defaultdict(list))
    checked = ok = bad = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json"))):
        bn = os.path.basename(f)
        if not bn.endswith("_t0.json") or ".dec." in bn:
            continue
        room = bn.split("_r")[0]
        if room not in rmap:
            continue
        stg, ts, rec = rmap[room]
        if a.since and ts < a.since:
            continue
        if arms_filter and stg not in arms_filter:
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        seats = j.get("seats") or []
        if len(seats) != 4:
            continue
        ids = [(x.get("user_id") or "") for x in seats]
        if ME not in ids:
            continue
        me = ids.index(ME)
        rr = j.get("rounds") or []
        groups = rounds_of(j)
        if not groups:
            continue
        for gi, cur in enumerate(groups):
            if gi >= len(rr):
                break
            our_tp = None
            our_melds = 0
            hands, nm, ng, turn = cur["hands"], cur["nm"], cur["ng"], cur["turn"]
            for e in cur["events"]:
                t, s = e.get("type"), e.get("seat")
                if t == "round_ended":
                    break
                if not isinstance(s, int) or not (0 <= s < 4):
                    continue
                if t == "tile_drawn":
                    hands[s].append(e.get("tile"))
                elif t == "tile_discarded":
                    x = e.get("tile")
                    if x in hands[s]:
                        hands[s].remove(x)
                    turn[s] += 1
                    if s == me and turn[s] <= a.maxturn and our_tp is None:
                        ex, gg = nm[s] + ng[s], ng[s]
                        try:
                            if ex_shanten(list(hands[s]), qidui=(ex == 0 and gg == 0),
                                          exposed_melds=ex, gangs=gg) == 0:
                                our_tp = turn[s]
                        except Exception:
                            pass
                elif t in ("chi", "peng", "gang"):
                    # ★ 必须维护副露计数（nm/ng）：否则 shanten() 会按"门清 13 张"判 12 张的手牌而报错
                    #   —— 这正是本工具首版把"8 巡听牌率"低估到 18%（真值 ~45%）的原因。
                    nm[s] += 1
                    if t == "gang":
                        ng[s] += 1
                    if s == me:
                        our_melds += 1
                    if t == "chi":
                        used = list((e.get("data") or {}).get("tiles") or [])
                        if e.get("tile") in used:
                            used.remove(e.get("tile"))
                        for x in used:
                            if x in hands[s]:
                                hands[s].remove(x)
                    elif t == "peng":
                        for _ in range(2):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
                    else:
                        for _ in range(3):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
            sc = rr[gi].get("scores") or []
            if len(sc) == 4:
                room_sum[room] += sc[me]
            x = S[stg]
            x[0] += 1
            x[4] += our_melds
            if rr[gi].get("winner") == me:
                x[5] += 1
                x[6] += rr[gi].get("multiplier") or 1
            if our_tp is not None:
                if our_tp <= 4:
                    x[1] += 1
                if our_tp <= 6:
                    x[2] += 1
                if our_tp <= a.maxturn:
                    x[3] += 1
            per_room[stg][room].append((1 if (our_tp is not None and our_tp <= a.maxturn) else 0,
                                        our_melds, 1 if rr[gi].get("winner") == me else 0))

    print("臂窗口 since=%s；房数（auto_ranking 命中）：%s" % (a.since or "-", {k: S[k][7] for k in S}))
    print("%-14s %6s %7s %8s %8s %8s %8s %9s %8s" %
          ("arm", "局", "%d巡听" % a.maxturn, "4巡听", "6巡听", "副露/局", "胡率", "番/胡", "(房)"))
    for stg in sorted(S):
        x = S[stg]
        n = max(1, x[0])
        print("%-14s %6d %7.1f%% %7.1f%% %7.1f%% %8.3f %7.2f%% %8.3f" %
              (stg, x[0], 100.0 * x[3] / n, 100.0 * x[1] / n, 100.0 * x[2] / n,
               x[4] / n, 100.0 * x[5] / n, x[6] / max(1, x[5])))
    # ★ 正面尺子校验：本工具逐房算出的"我方得分"必须等于 auto_ranking 的 total_score
    #   （§9.56 的教训：胡率≈25% 这类检查没有鉴别力，必须用**得分**对账）
    ok = bad = 0
    for room, tot in room_sum.items():
        rec = rmap.get(room)
        if not rec:
            continue
        mine = next((x for x in (rec[2].get("ranking") or []) if x.get("user_id") == ME), None)
        if mine is None:
            continue
        if abs(tot - float(mine.get("total_score") or 0)) <= 0.5:
            ok += 1
        else:
            bad += 1
    print("★ 尺子校验（本工具逐房我方得分 vs auto_ranking）：一致 %d / 不一致 %d = %.1f%%"
          % (ok, bad, 100.0 * ok / max(1, ok + bad)))
    print("注：逐局事件口径；%d 巡听 = 我方可≤%d 次出牌内达到向听 0 的局占比（含副露后）。" % (a.maxturn, a.maxturn))


if __name__ == "__main__":
    main()
