# -*- coding: utf-8 -*-
"""门清听牌差距：**是真棋力缺口，还是选择效应？**

问题（STATUS §9.66 分解）：8 巡听牌差距 6.94pp 里，副露占比（构成）只解释 2.51pp（36%），
层内差异 4.43pp（64%）。而层内那部分**可能是选择效应**（"门清/有副露"是打法的结果，不是随机分层）。

判据：**按住起手向听分档**后再比。若差距在各档内仍在 ⇒ 更像真棋力缺口；若消失 ⇒ 选择效应。

做法：门户复盘重建四家手牌（含补杠/暗杠的正确处理），对每个座位：
  · 起手向听（start_hands，13 张）
  · 第 8 次弃牌**之后**的手牌向听（==0 记为听牌）
  · 该次弃牌前是否已有副露
按 (组 × 起手向听档 × 有副露/门清) 汇总听牌率。有界采样 + 低优先级。
"""
from __future__ import annotations
import collections, glob, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower            # noqa: E402
print("lower ->", lower(idle=True), flush=True)
from mahjong.shanten_exact import shanten as SH
from meld_acceptance import ME, board_top   # noqa: E402

MAXF = 0            # 0 = 全量语料（与 §9.66 同口径）
# ★ 2026-09-17：可按策略族筛房。因为"我方"这一列是**混合策略**的——而 auto_ranking 显示
#   基线/其它 444 房 vs c135 族仅 26 房 ⇒ 全量口径量到的**主要是基线的缺口**。
#   切开后才能回答："c135 族（真进张打破并列）是否也补上了听牌速度缺口"。
C135_FAMILY = {"speedc135", "speedc142", "speedc143", "speedc145", "speedc146", "speedc147",
               "speedc148", "speedc150", "speedc151", "speedc152", "speedc153", "speedc154",
               "speedc155", "speedc156", "speedc159", "speedc159b", "speedc159c", "speedc162",
               "speedc163", "speedc164", "speedc165", "speedc166", "speedc167", "speedc168"}
FAM = sys.argv[1] if len(sys.argv) > 1 else ""
ROOM_STRAT = {}
for _ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
    _ln = _ln.strip()
    if not _ln:
        continue
    try:
        _d = json.loads(_ln)
    except Exception:
        continue
    if _d.get("room"):
        ROOM_STRAT[_d["room"]] = _d.get("strategy")

files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json")))
files = [f for f in files if ".dec." not in f]
if FAM:
    def _keep(f):
        st = ROOM_STRAT.get(os.path.basename(f).split("_r")[0])
        if st is None:
            return False
        return (st in C135_FAMILY) if FAM == "c135" else (st not in C135_FAMILY)
    files = [f for f in files if _keep(f)]
    print("按族筛选 %s ⇒ 文件 %d" % (FAM, len(files)))
if MAXF: files = files[-MAXF:]
board = board_top(16)
TOP = {u for _, u, _ in board}
print("复盘文件 %d ；top16 参照 %d 人" % (len(files), len(TOP)))

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

# 统计容器：组 -> 起手档 -> 副露档 -> [听牌数, 局数]
S = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0])))
mismatch = 0; rounds_seen = 0
for f in files:
    try: j = json.load(io.open(f, encoding="utf-8"))
    except Exception: continue
    if not isinstance(j, dict) or len(j.get("seats") or []) != 4: continue
    uids = [s.get("user_id") for s in j["seats"]]
    groups = {}
    for i, u in enumerate(uids):
        groups[i] = "我方" if u == ME else ("top16" if u in TOP else "其余")
    # ★ 一局跨多个 block（start_hands 只在第一块）⇒ 必须按 round_no 合并事件（§9.66 ① 的坑）
    byround = collections.defaultdict(list)
    for b in j.get("blocks") or []:
        if isinstance(b, dict):
            byround[b.get("round_no")].append(b)
    for rn in sorted(byround, key=lambda x: (x is None, x)):
        blks = sorted(byround[rn], key=lambda b: b.get("seq_start") or 0)
        sh = blks[0].get("start_hands")
        if not sh or len(sh) != 4 or any(not isinstance(h, list) for h in sh): continue
        evs = []
        for b in blks:
            evs.extend(b.get("events") or [])
        evs.sort(key=lambda e: e.get("seq", 0))
        hands = [list(h) for h in sh]; melds = [[] for _ in range(4)]
        start_sh = {}
        for i in range(4):
            try: start_sh[i] = SH(hands[i], qidui=True, exposed_melds=0, gangs=0)
            except Exception: start_sh[i] = None
        disc = [0]*4
        for e in evs:
            t = e.get("type"); s = e.get("seat")
            if t == "round_ended": break
            if s is None or not (0 <= s < 4): continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
            elif t == "tile_discarded":
                x = e.get("tile")
                if x in hands[s]: hands[s].remove(x)
                disc[s] += 1
                if disc[s] == 8 and start_sh[s] is not None:
                    ex = len(melds[s]); gg = sum(1 for m in melds[s] if m.get("type") == "gang")
                    if len(hands[s]) == 13 - 3*ex - gg:
                        rounds_seen += 1
                        try:
                            ten = 1 if SH(hands[s], qidui=(ex == 0 and gg == 0),
                                          exposed_melds=ex, gangs=gg) == 0 else 0
                        except Exception:
                            ten = 0
                        st = min(5, start_sh[s])
                        md = "有副露" if ex > 0 else "门清"
                        cell = S[groups[s]][st][md]
                        cell[0] += ten; cell[1] += 1
                    else:
                        mismatch += 1
            elif t in ("chi", "peng", "gang"):
                apply_meld(hands, melds, e)

print("可分析（第8次弃牌后手牌长度吻合）局数: %d ；长度不吻合: %d" % (rounds_seen, mismatch))
print()
print("%-6s %-8s %-8s %7s %9s" % ("组", "起手档", "副露档", "局数", "8巡听牌"))
for g in ("我方", "top16", "其余"):
    for st in sorted(S[g]):
        for md in ("门清", "有副露"):
            n, tot = S[g][st][md]
            if tot:
                print("%-6s %-8s %-8s %7d %8.1f%%" % (g, "向听%d" % st, md, tot, 100.0*n/tot))
print()
print("=== 分层对比（同一档起手 + 同一副露档）：我方 vs top16 ===")
print("%-8s %-8s %8s %8s %8s %8s" % ("起手档", "副露档", "我方率", "top16率", "差(pp)", "n(我/top)"))
for st in sorted(set(S["我方"]) | set(S["top16"])):
    for md in ("门清", "有副露"):
        a, na = S["我方"][st][md]
        b, nb = S["top16"][st][md]
        if na >= 60 and nb >= 60:
            pa, pb = 100.0*a/na, 100.0*b/nb
            print("%-8s %-8s %7.1f%% %7.1f%% %+7.1f %6d/%-5d" % ("向听%d" % st, md, pa, pb, pb-pa, na, nb))
