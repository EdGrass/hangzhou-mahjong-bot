# -*- coding: utf-8 -*-
"""副露"机会生产" vs "机会兑现"的分解：每 block 的**有资格窗口数**（E/blocks）我方 vs top-N。

动机（STATUS §4c-40/§4c-41 把缺口定位在"机会的生产"）：
  副露覆盖 = ①每局的**有资格窗口数**（手里有没有对子/搭子 → 能不能碰/吃） × ②窗口的接受率。
  §4c-40 只量了②（接受率 41.2% vs 60.0%）。①从来没量过——若我方 E/blocks 明显更低，
  那说明"机会生产"不足的根子在**弃牌把手形里的对子/搭子用掉了**，而不是门控太严。

口径与 meld_acceptance 一致（碰: 手里同牌 ≥2；吃: 下家有对应搭子），只额外做**按人归一**。
"""
from __future__ import annotations
import collections, glob, io, json, os, sys, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower            # noqa: E402
print("lower ->", lower(idle=True), flush=True)
from meld_acceptance import ME, board_top, chi_options   # noqa: E402

board = board_top(8)
top_uids = {u for _, u, _ in board}
E = collections.Counter(); B = collections.Counter(); A = collections.Counter()

for f in glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json")):
    try:
        j = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(j, dict) or len(j.get("seats") or []) != 4:
        continue
    uids = [s.get("user_id") for s in j["seats"]]
    for b in j.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        sh = b.get("start_hands")
        if not sh or len(sh) != 4 or any(not isinstance(h, list) for h in sh):
            continue
        for u in uids:
            B[u] += 1
        hands = [list(h) for h in sh]
        for e in b.get("events") or []:
            t = e.get("type"); s = e.get("seat")
            if t == "round_ended":
                continue
            if s is None or not (0 <= s < 4):
                continue
            if t == "tile_drawn":
                hands[s].append(e.get("tile"))
            elif t == "tile_discarded":
                x = e.get("tile")
                for i in range(4):
                    if i == s:
                        continue
                    pe = hands[i].count(x) >= 2
                    ce = (i == (s + 1) % 4) and chi_options(hands[i], x) > 0
                    if pe or ce:
                        E[uids[i]] += (1 if pe else 0) + (1 if ce else 0)
                if x in hands[s]:
                    hands[s].remove(x)
            elif t in ("chi", "peng", "gang"):
                data = e.get("data") or {}; tile = e.get("tile")
                if t == "chi":
                    used = False
                    for tl in (data.get("tiles") or []):
                        if tl == tile and not used:
                            used = True; continue
                        if tl in hands[s]: hands[s].remove(tl)
                elif t == "peng":
                    for _ in range(2):
                        if tile in hands[s]: hands[s].remove(tile)
                else:
                    kind = str(data.get("kind") or "ming")
                    n = {"an": 4, "bu": 1}.get(kind, 3)
                    for _ in range(n):
                        if tile in hands[s]: hands[s].remove(tile)
                A[uids[s]] += 1


def agg(uids_set, label):
    es = sum(E[u] for u in uids_set); bs = sum(B[u] for u in uids_set); as_ = sum(A[u] for u in uids_set)
    if bs:
        print("  %-16s blocks=%6d  E/blocks=%6.2f  A/blocks=%5.2f  接受率=%.1f%%"
              % (label, bs, es / bs, as_ / bs, 100.0 * as_ / max(1, es)))
    return es / bs if bs else 0.0


print("副露机会分解（E=有资格窗口数，按人按 block 归一）")
me_r = agg({ME}, "我方 EdGrass")
top_r = agg(top_uids, "榜单 top8")
oth = set(B) - {ME} - top_uids
ot_r = agg(oth, "其余玩家")
print("  ⇒ 我方 E/blocks 相对 top8：%+.2f%%" % (100.0 * (me_r / top_r - 1.0) if top_r else 0))
print("  ⇒ 我方 E/blocks 相对其余：%+.2f%%" % (100.0 * (me_r / ot_r - 1.0) if ot_r else 0))
