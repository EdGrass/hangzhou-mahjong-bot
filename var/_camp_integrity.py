import json, io, os, glob, collections
CAMP = "2026-09-20 14:54:07"
rows = [json.loads(l) for l in io.open("var/auto_ranking.jsonl", encoding="utf-8") if l.strip()]
camp = [d for d in rows if (d.get("ts") or "") >= CAMP and d.get("strategy") in ("speedtugc", "speedc151")]
byroom = collections.defaultdict(set)
for d in rows:
    if d.get("room") and d.get("strategy"):
        byroom[d["room"]].add(d["strategy"])
mixed = [r for r, s in byroom.items() if len(s) > 1]
have = set(os.path.basename(f).split("_r")[0] for f in glob.glob("var/replays/recent/*.json"))
crooms = [d["room"] for d in camp if d.get("room")]
cov = sum(1 for r in crooms if r in have)
print("本役完成房（两臂）=%d；唯一房=%d" % (len(camp), len(set(crooms))))
print("  其中已有门户复盘（recent）= %d（%.1f%%）" % (cov, 100.0 * cov / max(1, len(set(crooms)))))
print("  本役内【混臂房】（同一 room 出现多个 strategy）= %d" % len([r for r in set(crooms) if r in mixed]))
print("  全史混臂房 = %d（%s）" % (len(mixed), mixed[:4]))
bad = [d for d in camp if d.get("status") != "finished"]
print("  本役内非 finished 记录 = %d" % len(bad))
gp = [x.get("games_played") for d in camp for x in (d.get("ranking") or [])]
print("  games_played 取值分布 = %s" % collections.Counter(gp).most_common(4))
