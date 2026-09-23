# -*- coding: utf-8 -*-
"""`ladder_snapshot` —— 把门户口径的**榜单快照**追加到 `var/ladder_history.jsonl`，并给出趋势。

为什么需要：榜单是**累计分**（`total_score` 累加 ⇒ 每打一房就变），而门户只给"当前值" ⇒
没有时间序列就看不出"我们的斜率是多少、最近几天是在止血还是继续掉"。
本工具每次运行追加一行（**同一分钟同 period 去重**），并打印"自上次快照以来"的隐含 **分/房**。

用法：
    python -X utf8 tools/ladder_snapshot.py            # all + today + week 各记一行
    python -X utf8 tools/ladder_snapshot.py --periods all
    python -X utf8 tools/ladder_snapshot.py --show      # 只看趋势，不写入
"""
from __future__ import annotations
import argparse, io, json, os, ssl, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("HM_SERVER", "").strip() or "http://127.0.0.1:8080"
OUT = os.path.join(ROOT, "var", "ladder_history.jsonl")


def fetch(period, cookie, timeout=25):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request("%s/portal/api/leaderboard?period=%s" % (BASE, period),
                                 headers={"Cookie": cookie})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode("utf-8"))


def snapshot(period, j, ts=None):
    """把一份 leaderboard 响应压成一行记录（纯函数，便于单测）。"""
    me = j.get("me") or {}
    top = j.get("top") or []
    rooms = int(me.get("rooms") or 0)
    score = float(me.get("score") or 0)
    return {
        "ts": ts or time.strftime("%Y-%m-%d %H:%M:%S"),
        "period": period,
        "rank": me.get("rank"), "rooms": rooms, "score": score,
        "firsts": me.get("firsts"),
        "score_per_room": (score / rooms) if rooms else None,
        "top1_score": (top[0].get("score") if top else None),
    }


def load_history(path=OUT):
    rows = []
    try:
        with io.open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        rows.append(json.loads(ln))
                    except Exception:
                        pass
    except OSError:
        pass
    return rows


def trend(rows, period, n=5):
    """同一 period 的最近 n 条 ⇒ 相邻两条之间的隐含 分/房。"""
    v = [r for r in rows if r.get("period") == period]
    v.sort(key=lambda r: r.get("ts") or "")
    out = []
    for a, b in zip(v, v[1:]):
        dr = (b.get("rooms") or 0) - (a.get("rooms") or 0)
        ds = (b.get("score") or 0) - (a.get("score") or 0)
        out.append((a.get("ts"), b.get("ts"), dr, ds, (ds / dr if dr else None)))
    return v[-n:], out[-n:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--periods", default="all,today,week")
    ap.add_argument("--show", action="store_true", help="只读趋势，不追加")
    a = ap.parse_args()
    periods = [x.strip() for x in a.periods.split(",") if x.strip()]
    cookie = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
    rows = load_history()
    have = {(r.get("period"), (r.get("ts") or "")[:16]) for r in rows}
    new = []
    for i, p in enumerate(periods):
        try:
            j = fetch(p, cookie)
        except Exception as e:
            print("  %s 拉取失败：%s" % (p, str(e)[:80]))
            continue
        rec = snapshot(p, j)
        if not a.show and (rec["period"], rec["ts"][:16]) not in have:
            new.append(rec)
        time.sleep(1.2)
    if new:
        with io.open(OUT, "a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        rows.extend(new)
    print("榜单快照：新增 %d 行 → %s" % (len(new), OUT))
    for p in periods:
        v, tr = trend(rows, p)
        if not v:
            continue
        last = v[-1]
        print("  [%s] rank=%s rooms=%s score=%s（%.1f 分/房）firsts=%s" % (
            p, last.get("rank"), last.get("rooms"), last.get("score"),
            (last.get("score_per_room") or 0), last.get("firsts")))
        for ts0, ts1, dr, ds, spr in tr[-3:]:
            print("      %s → %s ：+%d 房，%+.0f 分 ⇒ %s 分/房" % (
                ts0[5:16], ts1[5:16], dr, ds, ("%.1f" % spr) if spr is not None else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
