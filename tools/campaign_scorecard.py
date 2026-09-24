# -*- coding: utf-8 -*-
"""campaign_scorecard \u2014\u2014 \u5b98\u65b9\u8d5b\u300c\u5f97\u5206\u7ed3\u6784\u300d\u8bb0\u5206\u5361\uff08\u8bfb\u95e8\u6237\u683c\u5f0f\u590d\u76d8\uff09\u3002

## \u4e3a\u4ec0\u4e48\u9700\u8981

`tools/hu_gap_split.py` \u7ed9\u7684\u662f**\u673a\u5236\u7387**\uff08\u80e1\u7387/\u542c\u724c\u7387/\u7206\u5934\u6001\u7387\uff09\uff1b\u4f46\u9009\u81c2\u4e0e\u590d\u76d8\u771f\u6b63\u8981\u56de\u7b54\u7684\u662f
**\u300c\u5206\u4ece\u54ea\u6765\u3001\u4e22\u5728\u54ea\u300d**\u3002\u540c\u4e00\u6279\u623f\u91cc\u53ea\u6709\u8fd9\u4e09\u6837\u4e1c\u897f\u80fd\u56de\u7b54\u5b83\uff1a

1. \u4e09\u7ec4\u5206/\u8f6e\uff08\u6211\u65b9 / \u540c\u6279\u699c\u5355 top32 / \u5176\u4ed6\uff09\uff1b
2. **\u7206\u5934\u8d26**\uff08\u6211\u65b9\u5f97\u624b\u51e0\u8f6e / \u88ab\u5bf9\u624b\u7206\u5934\u51e0\u8f6e\uff09\u4e0e**\u7ffb\u500d\u5c40\u6218\u7ee9**\uff08mult\u22652\uff09\uff1b
3. \u9010\u5c40\u6211\u65b9 vs **\u540c\u684c\u6700\u4f73**\u7684\u5dee\u3002

\u56db\u6d4b\u5b9e\u6d4b\uff08R1397\uff09\u5c31\u662f\u9760\u8fd9\u4e09\u6837\u624d\u770b\u51fa\u201c\u9891\u7387\u4e0d\u5dee\u3001\u7206\u5934\u51c0\u5dee\u201d\u7684\u3002\u4e4b\u524d\u662f\u4e34\u65f6\u811a\u672c\uff0c\u73b0\u5728\u56fa\u5b9a\u6210\u5de5\u5177\uff0c10/10 \u5f53\u665a\u76f4\u63a5\u8dd1\u540c\u4e00\u6761\u547d\u4ee4\u3002

## \u53e3\u5f84

- \u53ea\u8bfb `var/replays/<dirs>/<gid>.json`\uff08\u95e8\u6237\u683c\u5f0f\uff0c\u7531 `tools/fetch_tournament_replays.py` \u62c9\uff09\uff1b
- **\u4e00\u4e2a\u6587\u4ef6 = \u4e00\u5c40**\uff08\u5b98\u65b9 16 \u8f6e\uff1b\u8bad\u7ec3\u81ea\u52a8\u623f 8 \u8f6e\u2014\u2014**\u4e0d\u8981\u6df7\u7528**\uff09\uff1b
- \u5206/\u8f6e \u53ef\u4e0e\u5f79\u5185\u9608\u503c\u76f4\u63a5\u6bd4\uff1b\u5206/\u5c40 \u8981\u5148\u6309 `Rounds` \u5f52\u4e00\uff08\u672c\u5de5\u5177\u4e24\u4e2a\u90fd\u6253\uff09\uff1b
- top32 \u540d\u5355\u6765\u81ea\u95e8\u6237 `/portal/api/leaderboard?period=all`\uff08\u4e0e `hu_gap_split` \u540c\u6e90\uff09\uff1b
  \u53d6\u4e0d\u5230\uff08Cookie/\u7f51\u7edc\uff09\u6216 `--top32 0` \u65f6\u9000\u5316\u4e3a\u201c\u6211\u65b9 / \u5176\u4ed6\u201d\u4e24\u7ec4\uff0c**\u4e0d\u62a5\u9519**\u3002

## \u7528\u6cd5

    python -X utf8 tools/campaign_scorecard.py --dirs 4test_rooms
    python -X utf8 tools/campaign_scorecard.py --dirs \"official_1024_20260924_*\" --top32 0 --min-rounds 16
"""
from __future__ import annotations
import argparse
import collections
import glob
import io
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def board_top(n=32):
    """\u95e8\u6237\u5168\u91cf\u699c\u524d n \u540d {uid: rank}\uff1b\u4efb\u4f55\u5f02\u5e38\u90fd\u8fd4\u56de\u7a7a\uff08\u8ba9\u4e0b\u6e38\u9000\u5316\uff0c\u4e0d\u62a5\u9519\uff09\u3002"""
    if n <= 0:
        return {}
    try:
        import ssl
        import urllib.request
        ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"),
                     encoding="utf-8-sig").read().strip()
        req = urllib.request.Request(
            "https://10.240.169.190:18080/portal/api/leaderboard?period=all",
            headers={"Cookie": ck})
        with urllib.request.urlopen(req, timeout=25,
                                    context=ssl._create_unverified_context()) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return {p["user_id"]: p["rank"] for p in (d.get("top") or [])[:n] if p.get("user_id")}
    except Exception:
        return {}


def round_details(doc):
    """round_no -> {detail, fan}\uff08\u4ece `round_ended` \u4e8b\u4ef6\u91cc\u53d6\uff0cr\u4e0d\u53ef\u7f3a\uff09\u3002"""
    out = {}
    for b in doc.get("blocks") or []:
        for e in b.get("events") or []:
            if e.get("type") != "round_ended":
                continue
            dd = e.get("data") or {}
            out[dd.get("round_no")] = {"detail": dd.get("detail") or [],
                                       "fan": dd.get("fan"),
                                       "winner": e.get("seat")}
    return out


def load_file(path):
    """\u8bfb\u4e00\u4e2a\u590d\u76d8\u6587\u4ef6 \u2192 \u9010\u5e2d\u4f4d\u7edf\u8ba1 + \u9010\u8f6e\u8bb0\u5f55\uff08\u7eaf\u51fd\u6570\uff0c\u65b9\u4fbf\u5355\u6d4b\uff09\u3002"""
    with io.open(path, encoding="utf-8") as fh:
        doc = json.loads(fh.read())
    seats = [s.get("user_id") for s in (doc.get("seats") or [])]
    det = round_details(doc)
    per_seat = {i: {"rounds": 0, "score": 0, "wins": 0, "baotou_wins": 0,
                    "mult_wins": 0, "mult_losses": 0} for i in range(len(seats))}
    rounds = []
    for r in doc.get("rounds") or []:
        sc = r.get("scores") or []
        rno = r.get("round_no")
        info = det.get(rno) or {}
        detail = info.get("detail") or []
        win = r.get("winner")
        for i in range(min(len(sc), len(seats))):
            v = sc[i]
            if not isinstance(v, (int, float)):
                continue
            st = per_seat[i]
            st["rounds"] += 1
            st["score"] += v
            if win == i:
                st["wins"] += 1
                if "\u7206\u5934" in detail:
                    st["baotou_wins"] += 1
                if (r.get("multiplier") or 1) >= 2:
                    st["mult_wins"] += 1
            elif v < 0 and (r.get("multiplier") or 1) >= 2:
                st["mult_losses"] += 1
        rounds.append({"round_no": rno, "winner": win, "multiplier": r.get("multiplier") or 1,
                       "detail": detail, "scores": sc, "is_draw": r.get("is_draw")})
    return {"game": os.path.basename(path), "seats": seats, "per_seat": per_seat, "rounds": rounds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", required=True,
                    help="\u9017\u53f7\u5206\u9694\u7684 glob\uff08\u76f8\u5bf9 var/replays/\uff09\uff0c\u5982 4test_rooms")
    ap.add_argument("--top32", type=int, default=32, help="\u699c\u5355\u524d N \u4f5c\u4e3a\u5f3a\u624b\u7ec4\uff1b0=\u4e0d\u53d6\u699c\uff08\u53ea\u5206 \u6211\u65b9/\u5176\u4ed6\uff09")
    ap.add_argument("--min-rounds", type=int, default=16, help="\u8fdb\u5165\u201c\u9010\u4eba\u5206/\u8f6e\u201d\u8868\u6240\u9700\u6700\u5c11\u8f6e\u6570")
    a = ap.parse_args()

    files = []
    for g in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        files += sorted(glob.glob(os.path.join(ROOT, "var", "replays", g, "*.json")))
    if not files:
        print("\u274c \u6ca1\u627e\u5230\u590d\u76d8\u6587\u4ef6\uff08var/replays/%s/*.json\uff09\u21d2 \u4e0d\u7ed9\u7ed3\u8bba" % a.dirs)
        return 2
    top = board_top(a.top32)
    games = []
    for p in files:
        try:
            d = load_file(p)
        except Exception as e:
            print("  \u26a0 \u8df3\u8fc7 %s\uff08%s\uff09" % (os.path.basename(p), str(e)[:60]))
            continue
        if ME in d["seats"]:
            games.append(d)
    if not games:
        print("\u274c \u6ca1\u6709\u4efb\u4f55\u6587\u4ef6\u542b\u6211\u65b9 uid\uff08%s\uff09" % ME)
        return 2

    grp = {"me": {"rounds": 0, "score": 0, "wins": 0, "bt": 0, "games": 0},
           "top": {"rounds": 0, "score": 0, "wins": 0, "bt": 0, "games": 0},
           "oth": {"rounds": 0, "score": 0, "wins": 0, "bt": 0, "games": 0}}
    per_player = collections.defaultdict(lambda: {"rounds": 0, "score": 0, "wins": 0})
    me_win, me_loss = [], []
    me_bt_win = me_bt_loss = 0
    mult_wins = mult_losses = 0
    per_game = []
    for d in games:
        me = d["seats"].index(ME)
        sums = [0] * len(d["seats"])
        for r in d["rounds"]:
            sc = r["scores"]
            for i in range(min(len(sc), len(sums))):
                if isinstance(sc[i], (int, float)):
                    sums[i] += sc[i]
            w = r["winner"]
            if me < len(sc) and isinstance(sc[me], (int, float)):
                v = sc[me]
                if w == me:
                    me_win.append(v)
                    if "\u7206\u5934" in r["detail"]:
                        me_bt_win += 1
                    if r["multiplier"] >= 2:
                        mult_wins += 1
                elif v < 0:
                    me_loss.append(v)
                    if w is not None and "\u7206\u5934" in r["detail"]:
                        me_bt_loss += 1
                    if r["multiplier"] >= 2:
                        mult_losses += 1
        for i, uid in enumerate(d["seats"]):
            k = "me" if uid == ME else ("top" if uid in top else "oth")
            grp[k]["rounds"] += len(d["rounds"])
            grp[k]["score"] += sums[i]
            grp[k]["games"] += 1
            for r in d["rounds"]:
                if r["winner"] == i:
                    grp[k]["wins"] += 1
                    if "\u7206\u5934" in r["detail"]:
                        grp[k]["bt"] += 1
            pp = per_player[uid]
            pp["rounds"] += len(d["rounds"])
            pp["score"] += sums[i]
        best = max(sums) if sums else 0
        per_game.append((d["game"], sums[me], best))

    print("=" * 88)
    print("\u5b98\u65b9\u8d5b\u5f97\u5206\u7ed3\u6784\u8bb0\u5206\u5361\uff08\u95e8\u6237\u590d\u76d8 %s\uff09\u2014\u2014 \u5c40\u6570 %d" % (a.dirs, len(games)))
    print("=" * 88)
    label = {"me": "\u6211\u65b9", "top": "\u699c\u524d%d" % a.top32, "oth": "\u5176\u4ed6"}
    print("%-8s %6s %6s %10s %10s %8s %10s" % ("\u7ec4", "\u5e2d\u4f4d\u5c40", "\u8f6e", "\u603b\u5f97\u5206", "\u5206/\u8f6e", "\u80e1\u7387", "\u7206\u5934\u7387"))
    for k in ("me", "top", "oth"):
        g = grp[k]
        if not g["rounds"]:
            continue
        print("%-8s %6d %6d %+10d %+10.3f %7.1f%% %9.1f%%" % (
            label[k], g["games"], g["rounds"], g["score"], g["score"] / g["rounds"],
            100.0 * g["wins"] / g["rounds"], 100.0 * g["bt"] / g["rounds"]))
    if me_win or me_loss:
        print("\n\u6211\u65b9\u9010\u8f6e\u8d26\uff1a\u80e1 %d \u8f6e\uff08\u5747 %+.1f\uff09 / \u8d1f %d \u8f6e\uff08\u5747 %+.1f\uff09\uff1b"
              "\u7206\u5934\u5f97\u624b %d / \u88ab\u7206\u5934 %d\uff1b\u7ffb\u500d\u5c40 %d \u80dc / %d \u8d1f" % (
                  len(me_win), statistics.mean(me_win) if me_win else 0,
                  len(me_loss), statistics.mean(me_loss) if me_loss else 0,
                  me_bt_win, me_bt_loss, mult_wins, mult_losses))
    print("\n\u9010\u5c40\uff1a\u6211\u65b9 vs \u540c\u684c\u6700\u4f73")
    diffs = []
    for name, mine, best in per_game:
        diffs.append(mine - best)
        print("  %-36s \u6211\u65b9=%+4d  \u540c\u684c\u6700\u4f73=%+4d  \u5dee=%+4d" % (name, mine, best, mine - best))
    if per_game:
        print("  \u5408\u8ba1\uff1a\u6211\u65b9\u5747 %+.1f / \u540c\u684c\u6700\u4f73\u5747 %+.1f \u21d2 \u5747\u7f3a\u53e3 %+.1f" % (
            statistics.mean([x[1] for x in per_game]), statistics.mean([x[2] for x in per_game]),
            statistics.mean(diffs)))
    rows = sorted(((v["score"] / v["rounds"], uid, v["rounds"], v["score"])
                   for uid, v in per_player.items() if v["rounds"] >= a.min_rounds),
                  reverse=True)
    if rows:
        print("\n\u5206/\u8f6e\u6392\u884c\uff08\u2265%d \u8f6e\uff09\uff1a" % a.min_rounds)
        for rate, uid, n, s in rows[:10]:
            tag = "\u2190\u6211\u65b9" if uid == ME else ("\uff08\u699c#%s\uff09" % top.get(uid) if uid in top else "")
            print("  %+.3f  n=%3d  \u603b=%+5d  %s %s" % (rate, n, s, uid, tag))
        me_rate = per_player[ME]["score"] / max(1, per_player[ME]["rounds"])
        print("\n\u6211\u65b9 %.3f \u5206/\u8f6e\uff1b\u540c\u6279\u6700\u9ad8 %.3f \u5206/\u8f6e \u21d2 \u6211\u65b9\u4e3a\u5176 %.0f%%" % (
            me_rate, rows[0][0], 100.0 * me_rate / rows[0][0] if rows[0][0] else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())