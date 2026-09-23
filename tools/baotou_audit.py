# -*- coding: utf-8 -*-
"""爆头机会审计：在**我方真机窗口**上，找出「收下这次副露即可进入爆头(×2)」的机会，
并统计实际/现行策略有没有收。

爆头 = 摸牌前 13 张任意摸皆胡 → 番 ×2（fan.py 口径）。副露路径：e=3 组副露 +
暗手「1 面子 + 白孤」= 34 张万能听。这是可核算的**因果**机会（不是相关性）。
"""
import collections, glob, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bot.speedtu import _best_after_claim          # noqa: E402
from bot.speed import _chi_pairs, _melds_info      # noqa: E402

def to_view(rec):
    melds = []
    for it in rec.get("m") or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            k, t = it[0], it[1]
        elif isinstance(it, dict):
            k, t = it.get("type") or it.get("kind"), it.get("tile")
        else:
            continue
        if k in ("chi", "peng", "gang"):
            melds.append({"type": k, "tile": t, "tiles": [t] * (4 if k == "gang" else 3)})
    g = rec.get("god") or {}
    return {"seat": int(rec.get("s", -1)), "phase": rec.get("p") or "",
            "turn": int(rec.get("t", -1)), "responding_seats": list(rec.get("rs") or []),
            "my_hand": list(rec.get("h") or []), "melds": melds,
            "drawn_tile": rec.get("d"), "offer_tile": rec.get("o"),
            "god": {"baotou": bool(g.get("b")), "chain_count": int(g.get("cc") or 0),
                    "catch_play": bool(g.get("cp"))}, "all_melds": []}

def claim_options(v):
    """返回 [(kind, pair, after)]，after = _best_after_claim 结果。"""
    offer = v["offer_tile"]; hand = list(v["my_hand"])
    exposed, gangs = _melds_info(v)
    if len(hand) != 13 - 3 * exposed - gangs:
        return []
    out = []
    n = hand.count(offer)
    if n >= 3:
        a = _best_after_claim(hand, exposed, gangs, "gang_ming", offer)
        if a: out.append(("gang", None, a))
    if n >= 2:
        a = _best_after_claim(hand, exposed, gangs, "peng", offer)
        if a: out.append(("peng", None, a))
    if str(v["phase"]) == "response_chi":
        chi_cnt = sum(1 for m in v["melds"] if m.get("type") == "chi")
        if chi_cnt < 2:
            for pair in _chi_pairs(hand, offer):
                a = _best_after_claim(hand, exposed, gangs, "chi", offer, pair)
                if a: out.append(("chi", pair, a))
    return out

def main():
    files = sorted(glob.glob(os.path.join(ROOT, "var/replays/auto_*/*.dec.jsonl")))
    random.seed(3); files = random.sample(files, min(int(sys.argv[1]) if len(sys.argv) > 1 else 120, len(files)))
    st = collections.Counter(); samples = []
    for p in files:
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln: continue
            try: rec = json.loads(ln)
            except Exception: continue
            if not str(rec.get("p") or "").startswith("response_"): continue
            if not rec.get("o"): continue
            if int(rec.get("s", -1)) not in (rec.get("rs") or []): continue
            v = to_view(rec)
            opts = claim_options(v)
            if not opts: continue
            st["windows_with_claims"] += 1
            # 真机会 = 「现在还没爆头」且「收下后可进入爆头」
            exposed0, gangs0 = _melds_info(v)
            try:
                from mahjong.hu import is_baotou as _ib
                already = _ib(list(v["my_hand"]), allow_qidui=(exposed0 == 0 and gangs0 == 0),
                              exposed_melds=exposed0, gangs=gangs0)
            except Exception:
                already = False
            if already:
                st["already_baotou"] += 1
                continue
            bt = [o for o in opts if o[2][4]]            # after[4] = is_baotou
            if not bt:
                continue
            st["windows_with_baotou_claim"] += 1
            act = (rec.get("a") or {}).get("action")
            took = act in ("peng", "chi", "gang")
            if took: st["baotou_claim_taken"] += 1
            else:
                st["baotou_claim_missed"] += 1
                if len(samples) < 5: samples.append((rec, [o[0] for o in bt]))
            if len(v["my_hand"]) and v["my_hand"].count("白") >= 1:
                st["had_bai"] += 1
    w = max(1, st["windows_with_claims"])
    print("样本文件 %d" % len(files))
    print("有可收副露的窗口 %d" % st["windows_with_claims"])
    print("其中「收下即进入爆头(×2)」的窗口 %d (%.2f%% of claims-available)"
          % (st["windows_with_baotou_claim"], 100.0 * st["windows_with_baotou_claim"] / w))
    print("  实际收下 %d   漏掉 %d" % (st["baotou_claim_taken"], st["baotou_claim_missed"]))
    if st["windows_with_baotou_claim"]:
        print("  → 爆头机会收下率 %.1f%%"
              % (100.0 * st["baotou_claim_taken"] / st["windows_with_baotou_claim"]))
    for rec, kinds in samples:
        print("\n  [漏掉] %s %s hand=%s offer=%s melds=%s 可选=%s 实际=%s"
              % (rec.get("g"), rec.get("p"), rec.get("h"), rec.get("o"), rec.get("m"),
                 kinds, (rec.get("a") or {}).get("action")))

if __name__ == "__main__":
    main()
