# -*- coding: utf-8 -*-
"""批量拉取自动房全信息复盘：rooms 来自 var/auto_ranking.jsonl。
每房 /portal/api/test-rooms/{room} → games[] → 每 gid /portal/api/games/{gid}/events
→ 落盘 var/replays/server/<gid>.json。限速友好（1.2s 间隔 + 429 退避）。
"""
import glob
import json
import os
import ssl
import time
import urllib.request
import urllib.error

cookie = open("var/.portal_cookie", encoding="utf-8-sig").read().strip()
ctx = ssl._create_unverified_context()
base = "https://10.240.169.190:18080"
OUT = "var/replays/server"
os.makedirs(OUT, exist_ok=True)


def get(path, tries=4):
    for i in range(tries):
        req = urllib.request.Request(base + path, headers={"Cookie": cookie})
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.status == 429:
                time.sleep(6)
                continue
            return e.code, ""
        except Exception:
            time.sleep(3)
    return 429, ""


def main():
    rooms = []
    if os.path.exists("var/auto_ranking.jsonl"):
        for line in open("var/auto_ranking.jsonl", encoding="utf-8"):
            rec = json.loads(line)
            rooms.append((rec.get("room", ""), rec.get("strategy", "?")))
    print("rooms:", len(rooms), rooms)
    n_ok = n_fail = n_skip = 0
    for room, strat in rooms:
        if not room:
            continue
        s, b = get("/portal/api/test-rooms/%s" % room)
        if s != 200:
            print("room", room, "列表失败", s)
            n_fail += 1
            continue
        d = json.loads(b)
        gids = [g["game_id"] for g in (d.get("games") or [])
                if g.get("status") == "finished"]
        print("room", room, "games:", len(gids))
        for gid in gids:
            out = os.path.join(OUT, "%s.json" % gid)
            if os.path.exists(out):
                n_skip += 1
                continue
            s2, b2 = get("/portal/api/games/%s/events" % gid)
            if s2 == 200 and b2:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(b2)
                n_ok += 1
            else:
                print("  gid", gid, "失败", s2)
                n_fail += 1
            time.sleep(1.2)
        time.sleep(1.0)
    print("完成: 拉取 %d，失败 %d，跳过 %d" % (n_ok, n_fail, n_skip))


if __name__ == "__main__":
    main()
