# -*- coding: utf-8 -*-
"""真进张口径：**实选弃牌留下的进张数**，我方 vs 强者（按向听分层）。

为什么这样设计（便宜 5 倍）：逐候选算"遗憾"要 ~5 次 real_ukeire/决策（当年那个工具因此跑不完被强杀）；
而"实选弃牌后的进张数"只要 **1 次/决策**，按向听分层后同样能回答"谁的弃牌更好"。
配套记录"是否达到该手牌的最优进张"——但那需要候选最大值，故本脚本**只报 act_u 的分布**（诚实标注）。

有界采样 + lower()。
"""
import collections, glob, io, json, os, sys, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower
print("lower ->", lower(idle=True), flush=True)
from mahjong.shanten_exact import shanten as ex_shanten
from bot.ukeire import real_ukeire, visible_counts

ME = "u_7a3fba48d70b"
# ★ 关键混杂：我们的样本混合了策略——c135 族用真进张打破并列，speedtugc 族不用。
#   切开后才知"进张更差"是基线缺陷还是仍然存在。
C135_FAMILY = {"speedc135", "speedc142", "speedc143", "speedc145", "speedc146", "speedc147",
               "speedc148", "speedc150", "speedc151", "speedc152", "speedc153", "speedc154",
               "speedc155", "speedc156", "speedc159", "speedc159b", "speedc159c", "speedc162",
               "speedc163", "speedc164", "speedc165", "speedc166", "speedc167", "speedc168"}
ROOM_STRAT = {}
for _ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
    _ln = _ln.strip()
    if not _ln: continue
    try: _d = json.loads(_ln)
    except Exception: continue
    if _d.get("room"): ROOM_STRAT[_d["room"]] = _d.get("strategy")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 40
FAM = sys.argv[2] if len(sys.argv) > 2 else ""      # c135 / base / 空=全部
files = []
for d in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*"))):
    files.extend(sorted(glob.glob(os.path.join(d, "*_t0.json"))))
if FAM:
    def _room_of(path):
        return os.path.basename(path).split("_r")[0]   # 与组归属同一口径
    def _ok(path):
        st = ROOM_STRAT.get(_room_of(path))
        if st is None: return False
        return (st in C135_FAMILY) if FAM == "c135" else (st not in C135_FAMILY)
    files = [f for f in files if _ok(f)]
    print("按族筛选 %s ⇒ 文件 %d" % (FAM, len(files)))

def apply_meld(hands, nm, e):
    s = e["seat"]; t = e["type"]; data = e.get("data") or {}; tile = e.get("tile")
    if t == "chi":
        used = list(data.get("tiles") or [])
        if tile in used: used.remove(tile)
        for y in used:
            if y in hands[s]: hands[s].remove(y)
    elif t == "peng":
        for _ in range(2):
            if tile in hands[s]: hands[s].remove(tile)
    else:
        kind = str(data.get("kind") or "ming")
        n = {"an": 4, "bu": 1}.get(kind, 3)
        for _ in range(n):
            if tile in hands[s]: hands[s].remove(tile)
    nm[s] += 1

# 组 -> 向听 -> [act_u 列表]
G = collections.defaultdict(lambda: collections.defaultdict(list))
seen = set(); ng = 0; used = 0
for f in files:
    bn = os.path.basename(f)
    if ".dec." in bn: continue
    try: j = json.load(io.open(f, encoding="utf-8"))
    except Exception: continue
    seats = j.get("seats") or []
    ids = [(s.get("user_id") or "") for s in seats]
    if len(ids) != 4 or ME not in ids: continue
    gid = j.get("game_id") or bn
    if gid in seen: continue
    seen.add(gid); ng += 1
    if ng > LIMIT: break
    used += 1
    me = ids.index(ME)
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
        hands = [list(h) for h in sh0]; nm = [0]*4; ng_ = [0]*4; turn = [0]*4
        for e in evs:
            t, s = e.get("type"), e.get("seat")
            if t == "round_ended": break
            if not isinstance(s, int) or not (0 <= s < 4): continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
            elif t == "tile_discarded":
                x = e.get("tile")
                if 2 <= turn[s] + 1 <= 6 and len(hands[s]) == 14 - 3*nm[s] - ng_[s]:
                    if s == me:
                        _st = ROOM_STRAT.get(str(gid).split("_r")[0]) or ""
                        grp = "me135" if _st in C135_FAMILY else "mebase"
                    else:
                        grp = "strong"
                    rem = list(hands[s])
                    if x in rem:
                        rem.remove(x)            # 弃牌后 = 13-3e-g 张，才能算向听
                        try:
                            sh = ex_shanten(rem, qidui=(nm[s] == 0 and ng_[s] == 0),
                                            exposed_melds=nm[s], gangs=ng_[s])
                        except Exception:
                            sh = None
                        if sh is not None:
                            try:
                                vis = visible_counts(rem)
                                u = real_ukeire(rem, exposed=nm[s], gangs=ng_[s], visible=vis)[0]
                                if u is not None:
                                    G[grp][min(5, sh)].append(float(u))
                            except Exception:
                                pass
                if x in hands[s]: hands[s].remove(x)
                turn[s] += 1
            elif t in ("chi", "peng", "gang"):
                apply_meld(hands, nm, e)

print("样本 %d 场（第 2~6 巡出牌决策，真进张口径）" % used)
print("%-6s %-6s %8s %10s %10s %10s" % ("组", "向听", "决策", "平均进张", "中位", "=0占比"))
for grp in ("me135", "mebase", "strong"):
    for sh in sorted(G[grp]):
        v = G[grp][sh]
        if len(v) < 30: continue
        v.sort()
        print("%-6s %-6d %8d %10.2f %10.1f %9.1f%%" % (
            {"me135": "我方135", "mebase": "我方基线", "strong": "强者"}[grp], sh, len(v), st.mean(v), v[len(v)//2],
            100.0*sum(1 for a in v if a <= 0.001)/len(v)))
print()
print("=== 同向听对比 ===")
print("%-6s %10s %10s %9s %10s" % ("向听", "我方135", "强者", "差(张)", "n(我/强)"))
for sh in sorted(set(G["me135"]) | set(G["mebase"]) | set(G["strong"])):
    a, b = G["me135"].get(sh, []), G["strong"].get(sh, [])
    if len(a) >= 30 and len(b) >= 30:
        print("%-6d %10.2f %10.2f %+9.2f %6d/%-5d" % (sh, st.mean(a), st.mean(b), st.mean(b)-st.mean(a), len(a), len(b)))
