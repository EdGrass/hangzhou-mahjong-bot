# -*- coding: utf-8 -*-
"""策略级"实选弃牌的真进张"配对比较 —— 回答"如果 M>10，我们的快版兜底有多好"。

背景（13:40）：M>10 时 c135 家族（吃真进张算力）不可用，必须退回快版 c183。
但 c183 的路线是 c164（**不用真进张**），而 13:07/13:12 已证明**缺口的所在层正是真进张质量**。
⇒ 本工具在**同一批真实 draw 局面**上，比较各策略**实选弃牌**留下的真进张（配对比较，因此不受"房数少"限制）。

口径：对每个局面，取 hand(14 张含摸牌)；各策略 decide() 给出弃牌 d；算 real_ukeire(hand−d) 的 live 张数；
按弃牌后的向听分桶。**同一局面所有策略都算 ⇒ 配对**。有界采样 + lower()。
"""
import collections, glob, io, json, os, random, sys, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower
print("lower ->", lower(idle=True), flush=True)
from offline_replay import to_view
from mahjong.shanten_exact import shanten as SH
from bot.ukeire import real_ukeire, visible_counts
from run_bot import STRATEGY_FACTORIES as F

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
ARMS = ["speedtugc", "speedc167@1", "speedc167@2", "speedc159"]
paths = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
random.seed(7); random.shuffle(paths)
recs = []
for f in paths:
    for ln in io.open(f, encoding="utf-8"):
        ln = ln.strip()
        if not ln: continue
        try: r = json.loads(ln)
        except Exception: continue
        if r.get("p") == "draw" and r.get("d") and len(r.get("h") or []) == 14:
            recs.append(r)
        if len(recs) >= N: break
    if len(recs) >= N: break
print("配对局面:", len(recs))

def _build(spec):
    """支持 "speedc167@2" 形态（有界真进张的 topk）。"""
    if "@" in spec:
        name, k = spec.split("@", 1)
        cls = F[name]()
        return type(cls)(topk=int(k))
    return F[spec]()

pols = {a: _build(a) for a in ARMS}
# (arm, 向听) -> [act_u]；同时存每局面的各臂值以便配对
per = collections.defaultdict(lambda: collections.defaultdict(list))
pair = collections.defaultdict(lambda: collections.defaultdict(list))
for r in recs:
    v = to_view(r)
    hand = list(v.get("my_hand") or [])
    for a in ARMS:
        try:
            act = pols[a].decide(v) or {}
        except Exception:
            continue
        d = act.get("tile")
        if not d or d not in hand or act.get("action") not in ("discard", None, ""):
            continue
        rem = list(hand); rem.remove(d)
        try:
            s = SH(rem, qidui=True, exposed_melds=0, gangs=0)
        except Exception:
            continue
        try:
            u = real_ukeire(rem, visible=visible_counts(rem))[0]
        except Exception:
            continue
        if u is None: continue
        key = min(5, s)
        per[a][key].append(float(u))
        pair[key][a].append(float(u))

print()
print("%-12s %s" % ("策略", "  ".join("向听%d" % k for k in range(5))))
for a in ARMS:
    cells = []
    for k in range(5):
        vv = per[a].get(k) or []
        cells.append("%7.2f" % (st.mean(vv) if len(vv) >= 20 else float("nan")))
    print("%-12s %s" % (a, "  ".join(cells)))
print()
print("=== 配对差值（相对 speedtugc，同一批局面）===")
for k in range(5):
    base = pair[k].get("speedtugc") or []
    if len(base) < 20: continue
    for a in ARMS[1:]:
        cur = pair[k].get(a) or []
        n = min(len(base), len(cur))
        if n < 20: continue
        d = st.mean(cur[:n]) - st.mean(base[:n])
        print("  向听%d  %-11s Δ=%+.2f 张 (n=%d)" % (k, a, d, n))
