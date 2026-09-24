# -*- coding: utf-8 -*-
"""听牌缺口**在什么时候打开**？—— 同一手起手下，逐手累计"到第 k 手为止已听牌"的比例。

动机（13:21）：已证明听牌缺口**不是**弃牌质量（真进张）造成的。那么它是"开局塑造"还是"中盘适应"？
诊断法：在**同一起手向听档**内，比较我方 vs top16 的累计听牌曲线。
  · 缺口在 k=1~3 就出现 ⇒ 开局塑造（起手几手的取舍）
  · 缺口到 k=5~8 才出现 ⇒ 中盘适应（摸打与路线调整）
按 round_no 合并跨 block；有界采样 + lower()。
"""
import collections, glob, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower
print("lower ->", lower(idle=True), flush=True)
from mahjong.shanten_exact import shanten as SH
from meld_acceptance import ME, board_top

MAXF = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json")))
files = [f for f in files if ".dec." not in f][-MAXF:]
TOP = {u for _, u, _ in board_top(16)}
print("文件 %d ；top16 参照 %d 人" % (len(files), len(TOP)))

def apply_meld(hands, melds, e):
    s = e["seat"]; t = e["type"]; data = e.get("data") or {}; tile = e.get("tile")
    if t == "chi":
        tiles = list(data.get("tiles") or []); used = False
        for tl in tiles:
            if tl == tile and not used: used = True; continue
            if tl in hands[s]: hands[s].remove(tl)
        melds[s].append({"type": "chi", "tile": tile, "tiles": tiles})
    elif t == "peng":
        for _ in range(2):
            if tile in hands[s]: hands[s].remove(tile)
        melds[s].append({"type": "peng", "tile": tile, "tiles": [tile]*3})
    else:
        kind = str(data.get("kind") or "ming")
        if kind == "bu":
            if tile in hands[s]: hands[s].remove(tile)
            for m in melds[s]:
                if m.get("tile") == tile and m.get("type") == "peng":
                    m["type"] = "gang"; m["tiles"] = [tile]*4; break
            else: melds[s].append({"type": "gang", "tile": tile, "tiles": [tile]*4})
        else:
            n = 4 if kind == "an" else 3
            for _ in range(n):
                if tile in hands[s]: hands[s].remove(tile)
            melds[s].append({"type": "gang", "tile": tile, "tiles": [tile]*4})

# (组, 起手档) -> k -> [累计已达听牌数, 局数]
C = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
rounds = 0
for f in files:
    try: j = json.load(io.open(f, encoding="utf-8"))
    except Exception: continue
    if not isinstance(j, dict) or len(j.get("seats") or []) != 4: continue
    uids = [s.get("user_id") for s in j["seats"]]
    grp = ["我方" if u == ME else ("top16" if u in TOP else "其余") for u in uids]
    byround = collections.defaultdict(list)
    for b in j.get("blocks") or []:
        if isinstance(b, dict): byround[b.get("round_no")].append(b)
    for rn in sorted(byround, key=lambda x: (x is None, x)):
        blks = sorted(byround[rn], key=lambda b: b.get("seq_start") or 0)
        sh0 = blks[0].get("start_hands")
        if not sh0 or len(sh0) != 4: continue
        evs = []
        for b in blks: evs.extend(b.get("events") or [])
        evs.sort(key=lambda e: e.get("seq", 0))
        hands = [list(h) for h in sh0]; melds = [[] for _ in range(4)]
        st = []
        for i in range(4):
            try: st.append(min(5, SH(hands[i], qidui=True, exposed_melds=0, gangs=0)))
            except Exception: st.append(None)
        disc = [0]*4
        done = [False]*4           # 已经达到听牌（一旦达到就保持）
        for e in evs:
            t = e.get("type"); s = e.get("seat")
            if t == "round_ended": break
            if not isinstance(s, int) or not (0 <= s < 4): continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
            elif t == "tile_discarded":
                x = e.get("tile")
                if x in hands[s]: hands[s].remove(x)
                disc[s] += 1
                if st[s] is not None:
                    ex = len(melds[s]); gg = sum(1 for m in melds[s] if m.get("type") == "gang")
                    if not done[s] and len(hands[s]) == 13 - 3*ex - gg:
                        try:
                            if SH(hands[s], qidui=(ex == 0 and gg == 0),
                                  exposed_melds=ex, gangs=gg) == 0:
                                done[s] = True
                        except Exception:
                            pass
                    if disc[s] <= 8:
                        cell = C[(grp[s], st[s])][disc[s]]
                        cell[0] += 1 if done[s] else 0
                        cell[1] += 1
            elif t in ("chi", "peng", "gang"):
                apply_meld(hands, melds, e)
        rounds += 1

print("局数 %d" % rounds)
print()
print("=== 到第 k 手为止「已听牌」累计比例（同一手起手档内）===")
for grp in ("我方", "top16"):
    for bucket in (3, 4):
        row = []
        for k in range(1, 9):
            a, n = C[(grp, bucket)][k]
            row.append((100.0*a/n) if n else float("nan"))
        n_any = C[(grp, bucket)][8][1]
        if n_any >= 60:
            print("%-6s 起手向听%d (n=%4d): %s" % (grp, bucket, n_any,
                  "  ".join("k%d %.1f%%" % (k+1, v) for k, v in enumerate(row))))
print()
print("=== 逐手差距（top16 − 我方，pp）===")
for bucket in (3, 4):
    line = []
    for k in range(1, 9):
        a1, n1 = C[("我方", bucket)][k]; a2, n2 = C[("top16", bucket)][k]
        if n1 >= 60 and n2 >= 60:
            line.append("k%d %+.1f" % (k, 100.0*a2/n2 - 100.0*a1/n1))
    if line:
        print("起手向听%d : %s" % (bucket, "  ".join(line)))
