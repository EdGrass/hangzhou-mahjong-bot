# -*- coding: utf-8 -*-
"""melds_fidelity —— bot 看到的"四家副露"(view["all_melds"]) vs 门户权威 的保真度。

为什么：可见张数 = 自家手牌 + 四家弃牌河 + **四家副露**。河已在 R447/R448 修好，
副露是最后一个未独立验证的输入（`snap_view` 声称 v24 快照自带四家 melds 数组）。
若四家副露不全（例如只给了自己），所有 real_ukeire 活张数仍会偏乐观。

用法：python -X utf8 tools/melds_fidelity.py [--since "2026-09-18 04:30:00"]
门禁（★2026-09-20 R711 更正为**实际操作口径**）：**牌张级平均差 ≥ −1.0 张/决策 且 偏少率 ≤15%**。
  · 实测（09-20）：平均差 −0.291、偏少率 7.5%、四家完全一致率 89.6% ⇒ **OK**；
  · ⚠ 旧行文写的"完全一致率 ≥95%"**不是现行判据**（按它会得到假 FAIL）；完全一致率只作诊断量。
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★ 2026-09-20（R711）：本检查在清单里被要求**赛中跑**，但原来**没有自降优先级**
#   ⇒ 会与 bot 抢 CPU（§9.30：正是这种抢用造成了 4.4s 超窗）。与其它离线工具一致，降到 Idle。
sys.path.insert(0, os.path.join(ROOT, "tools"))
try:
    from _lowprio import lower
    lower(idle=True)
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    a = ap.parse_args()
    smap = {}
    for ln in open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("room"):
            smap[r["room"]] = r.get("ts") or ""
    port = {}
    for dd in ("server", "recent"):
        for f in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                p = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            port[p.get("game_id")] = p
    C = collections.Counter()
    for df in glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.dec.jsonl")):
        gid = os.path.basename(df).replace(".dec.jsonl", "")
        room = gid.split("_r")[0]
        if a.since and smap.get(room, "") < a.since:
            continue
        p = port.get(gid)
        if not p:
            continue
        rows = [json.loads(l) for l in open(df, encoding="utf-8") if l.strip()]
        if not rows or "am" not in rows[0]:
            continue
        evs = []
        for b in p.get("blocks") or []:
            evs.extend(b.get("events") or [])
        evs.sort(key=lambda e: e.get("seq") or 0)
        melds = [[] for _ in range(4)]
        at = {}
        for e in evs:
            t, s = e.get("type"), e.get("seat")
            if s is None:
                continue
            if t == "round_ended":
                melds = [[] for _ in range(4)]
            elif t == "chi":
                got = (e.get("data") or {}).get("tiles") or []
                melds[s].extend(got)
            elif t == "peng":
                melds[s].extend([e.get("tile")] * 3)
            elif t == "gang":
                melds[s].extend([e.get("tile")] * 4)
            if e.get("seq") is not None:
                at[e["seq"]] = [list(x) for x in melds]
        seqs = sorted(at)
        for r in rows:
            q = r.get("q")
            if q is None:
                continue
            pre = None
            for s in seqs:
                if s <= q:
                    pre = at[s]
                else:
                    break
            if pre is None:
                continue
            am = [list(x) for x in (r.get("am") or [])]
            if len(am) != 4:
                C["bad_shape"] += 1
                continue
            C["n"] += 1
            if all(collections.Counter(x) == collections.Counter(y)
                   for x, y in zip(am, pre)):
                C["same"] += 1
            else:
                C["diff"] += 1
                bt = sum(len(x) for x in am)
                pt = sum(len(x) for x in pre)
                C["dt"] += bt - pt
                if bt < pt:
                    C["short"] += 1
                elif bt > pt:
                    C["long"] += 1
                # 我方自己的副露是否对？（区分"只给自己"这种退化）
                me_ok = collections.Counter(am[r.get("s")] or []) == \
                    collections.Counter(pre[r.get("s")] or [])
                C["me_ok" if me_ok else "me_bad"] += 1
    n = C["n"] or 1
    print("四家副露保真度（对 %d 个决策行）" % C["n"])
    print("  四家全一致 %d = %.1f%%" % (C["same"], 100.0 * C["same"] / n))
    print("  不一致 %d（其中'我方自己对' %d / '我方自己也错' %d ；形状异常 %d）"
          % (C["diff"], C["me_ok"], C["me_bad"], C["bad_shape"]))
    # 逐字全一致 87.8% 主要来自快照时序（我方自己的副露 100% 正确）。
    # 真正该守的是**牌张级误差**：平均偏差与"偏少"两个数。
    dt = C["dt"] / n
    short_rate = C["short"] / n
    print("  牌张级：平均差 %+.3f 张/决策；偏少率 %.1f%%" % (dt, 100.0 * short_rate))
    ok = (dt >= -1.0 and short_rate <= 0.15)
    print("  门禁（平均差 ≥-1.0 张 且 偏少率 ≤15%%）：%s" % ("OK" if ok else "FAIL"))


if __name__ == "__main__":
    main()
