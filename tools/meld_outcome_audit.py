# -*- coding: utf-8 -*-
"""meld_outcome_audit —— 吃/碰的**结局层**核对：同一档 offer 上，"接受" vs "拒绝"的实际胡率。

为什么需要（§4c-47）：我们已测出**在"进张 +7 以上"的 offer 上我们只吃 11.4%、池内吃 20.8%**，但那是行为差异、不是因果。
本工具回答：**在那一档 offer 上，接受者与拒绝者的该局胡率差多少？**

口径（与 meld_ukeire_audit 一致）：
  - `delta = 接受后进张 − 不动进张`（进张 = 摸到后能降向听的牌张数）；
  - 每次弃牌产生一批窗口 → 记录"谁被给了什么档的 offer"；该玩家随后 1) 真的吃/碰 ⇒ 接受；2) 过了该轮 ⇒ 拒绝；
  - 每局结束时，按 (档, 阵营, 接受/拒绝) 统计该席**是否胡了这局**。

⚠ **观察性口径，非随机实验**：接受/拒绝是自选的 ⇒ 只能看方向与量级，不能当因果。定论仍需 A/B。

用法：python -X utf8 tools/meld_outcome_audit.py --dirs recent --limit 20 --max-turn 3
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
_s = importlib.util.spec_from_file_location("muo", os.path.join(ROOT, "tools", "meld_ukeire_audit.py"))
mu = importlib.util.module_from_spec(_s)
sys.modules["muo"] = mu
_s.loader.exec_module(mu)
moa = mu.moa
ME = moa.ME


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="recent")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-turn", type=int, default=3)
    a = ap.parse_args(argv)
    files = []
    for dd in [x.strip() for x in a.dirs.split(",") if x.strip()]:
        files += glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json"))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]
    # stat[bucket][side][acc] = [rounds_with_this_choice, wins]
    stat = collections.defaultdict(lambda: collections.defaultdict(lambda: [[0, 0], [0, 0]]))
    cnt = collections.Counter()
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        ids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
        if len(ids) != 4:
            continue
        me = ids.index(ME) if ME in ids else -1
        hands = [None] * 4
        nm = [0] * 4
        ng = [0] * 4
        turn = [0] * 4
        pend = {}
        recorded = []
        for b in d.get("blocks") or []:
            sh0 = b.get("start_hands")
            if sh0 and any(isinstance(x, (list, tuple)) for x in sh0):
                hands = [list(x) if isinstance(x, (list, tuple)) else [] for x in sh0]
                nm = [0] * 4
                ng = [0] * 4
                turn = [0] * 4
                pend = {}
                recorded = []
            if hands[0] is None:
                continue
            winner = None
            for e in b.get("events") or []:
                t, s = e.get("type"), e.get("seat")
                if t == "round_ended":
                    dat = e.get("data") or {}
                    if not dat.get("draw"):
                        winner = e.get("seat")
                    for seat, (bucket, side) in pend.items():
                        recorded.append((seat, bucket, side, 0))     # 窗口结束仍未响应 ⇒ 拒绝
                    for seat, bucket, side, acc in recorded:
                        cell = stat[bucket][side][acc]
                        cell[0] += 1
                        if winner == seat:
                            cell[1] += 1
                        cnt["settled"] += 1
                    recorded = []
                    hands = [None] * 4
                    pend = {}
                    continue
                if s is None or s < 0 or hands[s] is None:
                    continue
                if t == "tile_drawn":
                    hands[s].append(e.get("tile"))
                elif t == "tile_discarded":
                    tile = e.get("tile")
                    for o in range(4):
                        if o == s or hands[o] is None or turn[o] >= a.max_turn:
                            continue
                        ex, gg = nm[o] + ng[o], ng[o]
                        if moa.sh(list(hands[o]), ex, gg) is None:
                            continue
                        h = moa._canon13(hands[o], ex, gg)
                        base_u = moa.ukeire(h, ex, gg)
                        ups = [v for v in (mu.uke_after_one(hands[o], tile, "peng", ex, gg),
                                            mu.uke_after_one(hands[o], tile, "chi", ex, gg)) if v is not None]
                        if base_u is None or not ups:
                            continue
                        delta = max(ups) - base_u
                        bucket = "ge7" if delta >= 7 else ("pos" if delta > 0 else "le0")
                        pend[o] = (bucket, "me" if o == me else "pool")
                        cnt["offers"] += 1
                    if tile in hands[s]:
                        hands[s].remove(tile)
                    turn[s] += 1
                    pend.pop(s, None)
                elif t in ("pass", "timeout"):
                    if s in pend:
                        bucket, side = pend.pop(s)
                        recorded.append((s, bucket, side, 0))         # 拒绝：等该局结束再结算
                        cnt["declined_explicit"] += 1
                elif t in ("peng", "chi"):
                    if s in pend:
                        bucket, side = pend.pop(s)
                        recorded.append((s, bucket, side, 1))         # 接受：等该局结束再结算
                        cnt["accepted"] += 1
                    if t == "peng":
                        for _ in range(2):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
                        nm[s] += 1
                    else:
                        used = list((e.get("data") or {}).get("tiles") or [])
                        if e.get("tile") in used:
                            used.remove(e.get("tile"))
                        for x in used:
                            if x in hands[s]:
                                hands[s].remove(x)
                        nm[s] += 1
                elif t == "gang":
                    kind = (e.get("data") or {}).get("kind")
                    if kind == "bu":
                        if e.get("tile") in hands[s]:
                            hands[s].remove(e.get("tile"))
                        nm[s] -= 1
                        ng[s] += 1
                    else:
                        for _ in range(4 if kind == "an" else 3):
                            if e.get("tile") in hands[s]:
                                hands[s].remove(e.get("tile"))
                        ng[s] += 1
    print("=" * 78)
    print("吃/碰结局层核对（语料 %d 份，前 %d 巡）" % (len(files), a.max_turn))
    print("⚠ 观察性口径（接受/拒绝自选，非随机实验）；offers=%d accepted=%d declined=%d"
          % (cnt["offers"], cnt["accepted"], cnt["declined_explicit"] + cnt["declined_recorded"]))
    print("-" * 78)
    print("%-14s %-6s %-6s %8s %9s" % ("档位", "阵营", "选择", "样本", "该局胡率"))
    labels = {"ge7": "进张+7以上", "pos": "进张+1~6", "le0": "进张≤0"}
    for bucket in ("ge7", "pos", "le0"):
        for side in ("me", "pool"):
            for acc, nm2 in ((1, "接受"), (0, "拒绝")):
                n, w = stat[bucket][side][acc]
                if n:
                    print("%-14s %-6s %-6s %8d %8.1f%%" % (labels[bucket], side, nm2, n, 100.0 * w / n))
    print("=" * 78)


if __name__ == "__main__":
    main()
