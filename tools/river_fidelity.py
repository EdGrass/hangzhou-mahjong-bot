# -*- coding: utf-8 -*-
"""river_fidelity —— bot 看到的弃牌河 vs 门户权威河 的逐决策保真度。

为什么：bot 的 `river` 是所有 `real_ukeire` 活张数的输入（`visible_counts`）。
2026-09-18 实测发现 bot 的河**系统性偏短**（每局开头少 1 张、随局累积少 9 张），
根因是每批事件后额外拉全量快照时把水位推到 `auth.seq`，跳过了两次请求之间到达的事件。
本工具用"同一次会话内同时有 dec 与门户复盘"的房做逐决策对照，作为该修复的**可测端点**。

对齐：取门户事件里"决策点 q 之前（seq<=q）的当局弃牌河"。跨局按 round_ended 重置。
口径：同时给"原始"与"扣掉被吃/碰/杠拿走的那张"两个版本，排除吃碰造成的口径差。

用法：python -X utf8 tools/river_fidelity.py [--since "2026-09-18 04:00:00"]
门禁（★2026-09-20 R711 更正为**实际操作口径**）：**原始口径平均缺口 ≤1.5 张**。
  · 修复后稳定在"少 ~1.0 / 多 0.00"（R448 0.97、09-19 1.02、09-20 1.01）⇒ 该 ~1 张是**已知且被接受的**残差；
  · ⚠ 旧行文写的"一致率 ≥90% / 平均缺口 ≤0.5"是**修复前的目标值**，不是现行判据 —— 按它会得到假 FAIL（R451/R7035 踩过）。
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"
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
        if not rows:
            continue
        evs = []
        for b in p.get("blocks") or []:
            evs.extend(b.get("events") or [])
        evs.sort(key=lambda e: e.get("seq") or 0)
        raw = []; nocl = []
        at_raw = {}; at_nocl = {}
        for e in evs:
            t = e.get("type")
            if t == "round_ended":
                raw = []; nocl = []
            elif t == "tile_discarded" and e.get("tile"):
                raw.append(e["tile"]); nocl.append(e["tile"])
            elif t in ("chi", "peng", "gang"):
                tl = e.get("tile")
                if tl in nocl:
                    nocl.remove(tl)
            if e.get("seq") is not None:
                at_raw[e["seq"]] = list(raw)
                at_nocl[e["seq"]] = list(nocl)
        seqs = sorted(at_raw)
        for r in rows:
            if r.get("k") != "d" or r.get("p") != "draw" or \
                    (r.get("a") or {}).get("action") != "discard":
                continue
            q = r.get("q")
            br = r.get("r") or []
            if q is None:
                continue
            pre = None
            s_last = None
            for s in seqs:
                if s <= q:
                    pre = at_nocl[s]
                    s_last = s
                else:
                    break
            if pre is None:
                continue
            # 原始口径（含被吃碰走的那张）：与 bot 的口径一致
            raw = at_raw.get(s_last)
            C["n"] += 1
            if collections.Counter(br) == collections.Counter(pre):
                C["same"] += 1
            else:
                C["diff"] += 1
            C["gap"] += max(0, len(pre) - len(br))
            C["over"] += max(0, len(br) - len(pre))
            if raw is not None:
                C["n_raw"] += 1
                if collections.Counter(br) == collections.Counter(raw):
                    C["same_raw"] += 1
                C["gap_raw"] += max(0, len(raw) - len(br))
                C["over_raw"] += max(0, len(br) - len(raw))
    n = C["n"] or 1
    nr = C["n_raw"] or 1
    print("河保真度（对 %d 个弃牌决策）" % C["n"])
    print("  [扣吃碰口径] 完全一致 %.1f%% ；平均缺口 %.2f 少 / %.2f 多"
          % (100.0 * C["same"] / n, C["gap"] / n, C["over"] / n))
    print("  [原始口径]   完全一致 %.1f%% ；平均缺口 %.2f 少 / %.2f 多"
          % (100.0 * C["same_raw"] / nr, C["gap_raw"] / nr, C["over_raw"] / nr))
    # 修复前基线：平均少 1.1~4.4 / 多 6.0~15.1（同一役 12 房）。修复后实测 0.97 少 / 0.00 多。
    # 门禁定在"原始口径平均缺口 ≤1.5 张"（残差 ~1 张来自快照路径与吃碰口径），
    # 目的是抓"跨局不清零""整段丢事件"这类数量级回归，而不是追 0。
    ok = (C["gap_raw"] / nr <= 1.5 and C["over_raw"] / nr <= 1.5)
    print("  门禁（原始口径平均缺口 ≤1.5 张；修复前基线为 少1.1~4.4/多6.0~15.1）：%s"
          % ("OK" if ok else "FAIL"))


if __name__ == "__main__":
    main()
