import json, glob, os, collections
ROOT = "."
ME = "u_7a3fba48d70b"
smap = {}
for ln in open("var/auto_ranking.jsonl", encoding="utf-8"):
    ln = ln.strip()
    if not ln: continue
    try: d = json.loads(ln)
    except Exception: continue
    if d.get("room"): smap[d["room"]] = d.get("strategy") or "?"
S = collections.defaultdict(collections.Counter)
seen = set()
for dd in ("server", "recent"):
    for p in glob.glob("var/replays/%s/*.json" % dd):
        try: j = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        if not isinstance(j, dict): continue
        gid = j.get("game_id") or os.path.basename(p)
        if gid in seen: continue
        seats = j.get("seats") or []
        if len(seats) != 4: continue
        uids = [s.get("user_id") or "" for s in seats]
        if ME not in uids: continue
        seen.add(gid)
        me = uids.index(ME)
        room = gid.split("_r")[0]
        st = smap.get(room, "?")
        for b in j.get("blocks") or []:
            S[st]["rounds"] += 1
            for e in b.get("events") or []:
                if e.get("type") == "gang" and e.get("seat") == me:
                    k = (e.get("data") or {}).get("kind") or "?"
                    S[st]["g_" + k] += 1; S[st]["g_all"] += 1
                elif e.get("type") == "round_ended":
                    d = e.get("data") or {}
                    if not d.get("draw") and d.get("winner") == me:
                        S[st]["wins"] += 1
                        det = "|".join(str(x) for x in (d.get("detail") or []))
                        if "杠开" in det or "杠飘链" in det: S[st]["w_gang"] += 1
print("%-14s %7s %7s %8s %7s %7s %7s %7s" % ("strategy","局","胡","杠/轮","明/轮","补/轮","暗/轮","杠开/胡"))
for st, c in sorted(S.items(), key=lambda kv: -kv[1]["rounds"]):
    r = c["rounds"] or 1
    print("%-14s %7d %7d %8.4f %7.4f %7.4f %7.4f %7.2f%%" % (
        st, c["rounds"], c["wins"], c["g_all"]/r, c["g_ming"]/r, c["g_bu"]/r, c["g_an"]/r,
        100.0*c["w_gang"]/(c["wins"] or 1)))
