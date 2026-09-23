# -*- coding: utf-8 -*-
"""exec_leak_check —— 执行层"漏动作"总门禁（秒级，纯事件扫描）。

来源（2026-09-18）：发现"庄家开局首弃"因**没有前置事件可唤醒**而被服务端代打 48%
（top32 9.35%），修复后降到 ~5%（见 journal R438~R440）。本工具把整族审计固化成
一条命令，便于每次心跳/每 2~4 小时复核。

判定：一次弃牌后 1~2 条内出现**同席** `timeout{kind:"discard"}` ⇒ 该次为服务端代打。
分类：按"该次弃牌前面最近一条本人事件"分成 新局首动作 / 自己摸牌后 / 自己吃碰后 /
      自己弃牌后 / 自己杠后。

用法：
    python -X utf8 tools/exec_leak_check.py                      # 全量
    python -X utf8 tools/exec_leak_check.py --since "2026-09-18 01:40:00"
门禁（正式赛前）：新局首动作 ≤12%、整体我方弃牌代打 ≤1.0%。
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def board_top(n=32):
    try:
        ctx = ssl._create_unverified_context()
        ck = open(os.path.join(ROOT, "var", ".portal_cookie"),
                  encoding="utf-8-sig").read().strip()
        req = urllib.request.Request(
            "<平台地址>/portal/api/leaderboard?period=all",
            headers={"Cookie": ck})
        d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx)
                       .read().decode("utf-8"))
        return {p["user_id"] for p in (d.get("top") or [])[:n]}
    except Exception:
        return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--dirs", default="server,recent")
    a = ap.parse_args()
    top = board_top(32)
    smap = {}
    for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("room"):
            smap[r["room"]] = (r.get("strategy") or "?", r.get("ts") or "")
    kindC = collections.defaultdict(collections.Counter)
    grpC = collections.defaultdict(collections.Counter)
    seen = set()
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        for f in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                p = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            gid = p.get("game_id") or ""
            if not gid or gid in seen:
                continue
            info = smap.get(gid.split("_r")[0])
            if a.since and (not info or info[1] < a.since):
                continue
            seats = p.get("seats") or []
            if len(seats) != 4:
                continue
            uids = [s.get("user_id") or "" for s in seats]
            seen.add(gid)
            for b in p.get("blocks") or []:
                evs = b.get("events") or []
                for i, e in enumerate(evs):
                    if e.get("type") != "tile_discarded":
                        continue
                    s = e.get("seat")
                    if s is None or not (0 <= s < 4):
                        continue
                    u = uids[s]
                    g = "me" if u == ME else ("top" if u in top else "oth")
                    tmo = any(e2.get("type") == "timeout" and e2.get("seat") == s and
                              (e2.get("data") or {}).get("kind") == "discard"
                              for e2 in evs[i + 1:i + 3])
                    grpC[g]["n"] += 1
                    grpC[g]["tmo"] += 1 if tmo else 0
                    if g != "me":
                        continue
                    kind = "?"
                    for j in range(i - 1, -1, -1):
                        pe = evs[j]
                        if pe.get("seat") != s:
                            continue
                        t = pe.get("type")
                        if t == "tile_drawn":
                            kind = "自己摸牌后"
                            break
                        if t in ("chi", "peng"):
                            kind = "自己吃/碰后"
                            break
                        if t == "gang":
                            kind = "自己杠后"
                            break
                        if t == "tile_discarded":
                            kind = "自己弃牌后"
                            break
                    if kind == "?":
                        kind = "★新局首动作"
                    kindC[kind]["n"] += 1
                    kindC[kind]["tmo"] += 1 if tmo else 0
    print("=" * 76)
    print("执行层漏动作门禁（去重 %d 场%s）" %
          (len(seen), ("，since=" + a.since) if a.since else ""))
    print("=" * 76)
    print("%-10s %9s %8s %9s" % ("组", "弃牌", "代打", "代打率"))
    for g, lab in (("me", "我方"), ("top", "top32"), ("oth", "其他")):
        c = grpC[g]
        print("%-10s %9d %8d %8.2f%%" % (lab, c["n"], c["tmo"],
                                         100.0 * c["tmo"] / max(1, c["n"])))
    print()
    print("我方按情形：")
    print("%-16s %9s %8s %9s" % ("情形", "弃牌", "代打", "代打率"))
    for k, c in sorted(kindC.items(), key=lambda kv: -kv[1]["n"]):
        print("%-16s %9d %8d %8.2f%%" % (k, c["n"], c["tmo"],
                                         100.0 * c["tmo"] / max(1, c["n"])))
    m = kindC.get("★新局首动作", collections.Counter())
    r1 = 100.0 * m["tmo"] / max(1, m["n"])
    r2 = 100.0 * grpC["me"]["tmo"] / max(1, grpC["me"]["n"])
    print()
    print("门禁：新局首动作 %.2f%%（阈值 ≤12%%）%s ；整体 %.2f%%（阈值 ≤1.0%%）%s"
          % (r1, "OK" if r1 <= 12 else "FAIL", r2, "OK" if r2 <= 1.0 else "FAIL"))


if __name__ == "__main__":
    main()
