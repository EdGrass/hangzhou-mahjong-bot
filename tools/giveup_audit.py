# -*- coding: utf-8 -*-
"""giveup_audit —— C036「弃胡换爆头」的真实结局审计（附自校验）。

回答三个问题（全部只用**真实复盘**，不用 sim、不用代理指标）：
  1) 我方每次「摸牌可胡却出牌」（=弃胡）到底赚不赚：把「当时就胡的收益」与
     「该局我方真实得分」逐事件对比；
  2) 弃胡后本局仍由我方胡回的比例（= C036 里 P_conv 的真机值）；
  3) 反方向缺口：本可弃胡（转爆头且番翻倍）却直接胡掉的局数，并按我方历史策略归因。

自校验（先证尺子再量，缺一不可）：
  - 每局 `scores` 和必须为 0；
  - 对每个「我方真胡」局，用重建手牌算 `fan × (庄24/闲10)` 与服务器记分比对（期望 >99%）。

原理：`var/replays/{server,recent}/*.json` 的 `blocks[].start_hands` 给出**四家起手**，
`tile_drawn` 给出**四家牌面**，因此可逐局重建任意一家的手牌历史。

用法：
    python -X utf8 tools/giveup_audit.py                 # 主口径（含赔付自校验）
    python -X utf8 tools/giveup_audit.py --missed        # 追加「本该弃胡却胡掉」缺口
    python -X utf8 tools/giveup_audit.py --by-strategy   # 按 var/auto_ranking.jsonl 的策略归属分组
    python -X utf8 tools/giveup_audit.py --limit 400     # 只取最近 N 个复盘文件（调试用）
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.fan import calc as calc_fan          # noqa: E402
from mahjong.hu import is_baotou, is_win          # noqa: E402

ME_UID = "u_7a3fba48d70b"
P_CONV = 0.71


def _strategies():
    m = {}
    p = os.path.join(ROOT, "var/auto_ranking.jsonl")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("room"):
                m[d["room"]] = d.get("strategy") or "?"
    return m


def scan(path, want_missed=False):
    """返回 list[dict]：每局一条。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    seats = d.get("seats") or []
    us = [i for i, s in enumerate(seats) if (s.get("user_id") or "") == ME_UID]
    if not us:
        return None
    me = us[0]
    out = []
    hands = [None] * 4
    nm = [0] * 4; ng = [0] * 4; chain = [0] * 4; piao = [0] * 4
    pend = None          # 本轮刚发生的「可胡但未胡」
    declines = []
    taken = None
    for b in d.get("blocks") or []:
        sh = b.get("start_hands")
        if sh and any(isinstance(x, (list, tuple)) for x in sh):
            hands = [list(x) if isinstance(x, (list, tuple)) else [] for x in sh]
            nm = [0] * 4; ng = [0] * 4; chain = [0] * 4; piao = [0] * 4
            pend = None; declines = []; taken = None
        for e in b.get("events") or []:
            t, s = e.get("type"), e.get("seat")
            if t == "round_ended":
                data = dict(e.get("data") or {})
                data["_wseat"] = e.get("seat")
                if s == me and not data.get("draw") and pend is not None:
                    taken = pend                     # 这一局的「真胡」= 我们把它胡掉了
                rec = {"me": me, "end": data, "declines": declines, "taken": taken}
                if want_missed and taken is not None:
                    rec["missed"] = _missed_decline(taken)
                out.append(rec)
                hands = [None] * 4
                pend = None; declines = []; taken = None
                continue
            if s is None or s < 0 or hands[0] is None:
                continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
                if s == me:
                    ex, gg = nm[s] + ng[s], ng[s]
                    pend = None
                    try:
                        if is_win(list(hands[s]), exposed_melds=ex, gangs=gg):
                            info = calc_fan(list(hands[s][:-1]), hands[s][-1],
                                            {"count": chain[s], "piao": piao[s]},
                                            exposed_melds=ex, gangs=gg)
                            pend = {"fan": info["fan"], "detail": info["detail"],
                                    "hand": list(hands[s]), "draw": hands[s][-1],
                                    "ex": ex, "gg": gg, "chain": chain[s],
                                    "piao": piao[s], "dealer": None}
                    except Exception:
                        pend = None
            elif t == "tile_discarded":
                if e.get("tile") in hands[s]:
                    hands[s].remove(e.get("tile"))
                else:
                    continue
                if s == me:
                    if pend is not None:
                        declines.append(pend)      # 可胡却出牌 = 弃胡
                    pend = None
                chain[s] = 0; piao[s] = 0
            elif t == "peng":
                for _ in range(2):
                    if e.get("tile") in hands[s]:
                        hands[s].remove(e.get("tile"))
                    else:
                        break
                nm[s] += 1
                if s == me: pend = None
            elif t == "chi":
                used = list((e.get("data") or {}).get("tiles") or [])
                if e.get("tile") in used: used.remove(e.get("tile"))
                for x in used:
                    if x in hands[s]: hands[s].remove(x)
                    else: break
                nm[s] += 1
                if s == me: pend = None
            elif t == "gang":
                kind = (e.get("data") or {}).get("kind")
                if kind == "bu":
                    if e.get("tile") in hands[s]: hands[s].remove(e.get("tile"))
                    nm[s] -= 1; ng[s] += 1
                else:
                    for _ in range(4 if kind == "an" else 3):
                        if e.get("tile") in hands[s]: hands[s].remove(e.get("tile"))
                        else: break
                    ng[s] += 1
                chain[s] += 1
                if s == me: pend = None
    return out


def _missed_decline(taken):
    """该「真胡」局是否存在更好的弃胡（转爆头且 P_conv×番 > 现在番）。"""
    ex, gg, h14 = taken["ex"], taken["gg"], list(taken["hand"])
    for dd in sorted(set(h14)):
        h13 = list(h14); h13.remove(dd)
        try:
            if not is_baotou(h13, allow_qidui=(ex == 0 and gg == 0),
                             exposed_melds=ex, gangs=gg):
                continue
            info = calc_fan(h13, taken["draw"], {"count": taken["chain"], "piao": taken["piao"]},
                            exposed_melds=ex, gangs=gg)
            fb = info.get("fan")
            if info.get("hu") and fb and fb > taken["fan"] and P_CONV * fb > taken["fan"]:
                return (dd, fb)
        except Exception:
            continue
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--by-strategy", action="store_true")
    ap.add_argument("--missed", action="store_true")
    a = ap.parse_args(argv)
    files = sorted(glob.glob(os.path.join(ROOT, "var/replays/server/*.json"))) + \
            sorted(glob.glob(os.path.join(ROOT, "var/replays/recent/*.json")))
    if a.limit:
        files = files[-a.limit:]
    strat = _strategies() if a.by_strategy else {}
    tot = collections.Counter()
    acc = collections.defaultdict(collections.Counter)
    for p in files:
        recs = scan(p, want_missed=a.missed)
        if not recs:
            continue
        gid = os.path.basename(p).split("_r")[0]
        sk = strat.get(gid, "(older)") if a.by_strategy else "ALL"
        for r in recs:
            end, me = r["end"], r["me"]
            sc = end.get("scores") or []
            if len(sc) != 4:
                continue
            tot["rounds"] += 1
            acc[sk]["rounds"] += 1
            if sum(sc) != 0:
                tot["bad_scores"] += 1
            if r["taken"] is not None and end.get("_wseat") == me and not end.get("draw"):
                exp = r["taken"]["fan"] * (24 if end.get("dealer") == me else 10)
                tot["wins"] += 1
                acc[sk]["wins"] += 1
                if exp == sc[me]:
                    tot["pay_match"] += 1
                    acc[sk]["pay_match"] += 1
            for x in r["declines"]:
                win_now = x["fan"] * (24 if end.get("dealer") == me else 10)
                tot["declines"] += 1
                tot["now"] += win_now
                tot["real"] += sc[me]
                acc[sk]["declines"] += 1
                acc[sk]["now"] += win_now
                acc[sk]["real"] += sc[me]
                if end.get("_wseat") == me and not end.get("draw"):
                    tot["back"] += 1
                    acc[sk]["back"] += 1
            if a.missed and r.get("missed"):
                tot["missed"] += 1
                acc[sk]["missed"] += 1
    n = max(1, tot["declines"])
    print("我方局数=%d  scores 和≠0: %d" % (tot["rounds"], tot["bad_scores"]))
    print("赔付自校验：真胡 %d，重建 fan×赔付 与服务器一致 %d（%.2f%%）"
          % (tot["wins"], tot["pay_match"], 100.0 * tot["pay_match"] / max(1, tot["wins"])))
    print("弃胡事件 %d：现在就胡 +%d，实际 %+d，差 %+d（%+.2f/次）；胡回 %d/%d=%.0f%%"
          % (tot["declines"], tot["now"], tot["real"], tot["real"] - tot["now"],
             (tot["real"] - tot["now"]) / n, tot["back"], tot["declines"],
             100.0 * tot["back"] / n))
    if a.missed:
        print("本该弃胡却胡掉（缺口）=%d  （占真胡 %.2f%%）"
              % (tot["missed"], 100.0 * tot["missed"] / max(1, tot["wins"])))
    if a.by_strategy:
        print("\n%-18s %7s %7s %9s %10s %7s" % ("strategy", "rounds", "decis", "now", "real", "back%"))
        for sk in sorted(acc, key=lambda k: -acc[k]["rounds"]):
            v = acc[sk]
            d = max(1, v["declines"])
            print("%-18s %7d %7d %9d %10d %6.0f%%"
                  % (sk, v["rounds"], v["declines"], v["now"], v["real"],
                     100.0 * v["back"] / d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
