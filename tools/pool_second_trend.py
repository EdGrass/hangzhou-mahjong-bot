# -*- coding: utf-8 -*-
"""`pool_second_trend` —— 入席秒 ↔ 同桌强度 的**趋势**读数（只读，不占房、不改任何开关）。

⚠ 2026-09-17 12:4x **更正**：本工具第一版把"入席秒 >=54 vs <=51"的差（-50.2）当成
"50 -> 58 的增量"，这是**错的**——那个对比的分母含了大量"更早入席"的房，量到的其实是
**已经成立的"等待 vs 立即"效应**，不是"等更久"的增量。正确的增量对照必须**同臂内**做：
`50-53 秒` vs `54-59 秒`。实测（立即臂，准随机）：对手强度 Δ=-19.8 (t=-0.53)、Δ(50-54 vs 55-59)=-36.8 (t=-0.98)
⇒ **"58 比 50 好"目前不成立**，只是暗示（样本太小）。

本工具现在给出**两层对照**，请按标签读：

  A) **增量对照（同臂内，正确）**：限定单一策略的房，比 `<=lo` 与 `>=hi` 两个秒档。
     这才是"全局 wait 从 50 改到 58 值不值得"的证据；它**不受臂混杂影响**。
  B) **参考对照（臂间，已知结论）**：`<50` vs `>=50`（含 speedtugc / speedtugc_w50 两臂）。
     这是**已成立的随机化操纵效应**，回答的是"要不要等"，**不是**"要不要等更久"。

其它背景：
- 已成立的操纵实验：入席秒 >=50 的桌比"立即入席"**弱 49.3 分**（t=-4.24；去掉前 3 名贡献对手后仍 -33.7，t=-3.46；
  15 个小时里 13 个**同小时内部**仍是负向 ⇒ 不是时段混杂）。全局已启用 wait=50。
- **但该效应在"我方分/房"端点上还没显著**（+9.9/房，t=+0.38）⇒ 池子至今只有**代理端点**（对手强度）的证据，
  换算成分数只能用斜率外推，**没有随机化的直接验证**。

它做三件事：
  1) 按入席秒分桶，给出各桶的**同桌强度**与样本量；
  2) 做 >=54 vs <=51 的对照（差 ±2σ / t）；
  3) 用实测斜率把"对手强度差"**换算成我方分/房**（斜率由同一批房回归得到，不是拍的）。

用法（可随时跑，样本随战役自然增长）：
    python -X utf8 tools/pool_second_trend.py
    python -X utf8 tools/pool_second_trend.py --lo 51 --hi 54
"""
from __future__ import annotations
import argparse, collections, datetime as dt, glob, io, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower          # noqa: E402
print("lower ->", lower(idle=True), flush=True)

ME = "u_7a3fba48d70b"


def load_rows():
    out = []
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def room_seconds():
    """房 -> 入席秒。口径 = 复盘目录名 `auto_YYYYMMDD_HHMMSS`（match_super 在**等待之后**取 stamp）。"""
    out = {}
    for dp in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*"))):
        n = os.path.basename(dp)
        try:
            t = dt.datetime.strptime(n[5:20], "%Y%m%d_%H%M%S")
        except Exception:
            continue
        for fn in os.listdir(dp):
            room = fn.split("_r")[0]
            if room:
                out.setdefault(room, t.second)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=int, default=51, help="低桶上界（含）")
    ap.add_argument("--hi", type=int, default=54, help="高桶下界（含）")
    ap.add_argument("--since", default="2026-09-16 23:19:47",
                    help="B 的同期窗口起点（默认=池子实验开始）；空串=全时段（会有时段混杂）")
    ap.add_argument("--within", default="speedtugc",
                    help="增量对照限定在这个策略的房内（默认立即臂 speedtugc）；空串=不限定")
    a = ap.parse_args()
    rows = load_rows()
    secs = room_seconds()
    # 对手强度：前缀历史均分（>=3 房才计入），与 _pool_composition 同法
    prefix, data = {}, []
    for d in sorted([r for r in rows if r.get("room")], key=lambda r: r.get("ts") or ""):
        rk = d.get("ranking") or []
        mine = next((x for x in rk if x.get("user_id") == ME), None)
        if mine is None or len(rk) != 4:
            continue
        vals = []
        for x in rk:
            if x.get("user_id") == ME:
                continue
            s = prefix.get(x.get("user_id"))
            if s and s[1] >= 3:
                vals.append(s[0] / s[1])
        if vals:
            others = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME]
            data.append({"room": d["room"], "st": d.get("strategy"), "ts": d.get("ts"), "opp": sum(vals) / len(vals),
                         "net": (mine.get("total_score") or 0) - sum(others) / 3.0,
                         "sec": secs.get(d["room"])})
        for x in rk:
            try:
                sc = float(x.get("total_score"))
            except Exception:
                continue
            s = prefix.setdefault(x.get("user_id"), [0.0, 0])
            s[0] += sc; s[1] += 1

    have = [d for d in data if d["sec"] is not None]
    print("可分析房 %d（其中能定位入席秒 %d）" % (len(data), len(have)))
    if len(have) < 10:
        print("样本不足，等战役继续积累。")
        return 0

    # 斜率：我方分/房 ~ 对手强度
    xs = [d["opp"] for d in data]; ys = [d["net"] for d in data]
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx > 0:
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        resid = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
        se_b = (sum(r * r for r in resid) / max(1, len(xs) - 2) / sxx) ** 0.5
        print("斜率：对手每弱 1 分 ⇒ 我方分/房 %+.3f（SE %.3f, t=%+.2f）" % (-b, se_b, b / se_b if se_b else 0))
    else:
        b = 0.0
        print("斜率：样本退化，取 0")

    buck = collections.defaultdict(list)
    for d in have:
        buck[d["sec"]].append(d)
    print("入席秒 : 房数  同桌强度   我方分/房")
    for s in sorted(buck):
        v = buck[s]
        print("  %2d 秒 : %4d  %+9.1f  %+10.1f" % (s, len(v), st.mean([x["opp"] for x in v]),
                                                    st.mean([x["net"] for x in v])))


    def contrast(sel, label, lo_rng, hi_rng):
        lo = [d for d in data if sel(d) and d["sec"] is not None and lo_rng[0] <= d["sec"] <= lo_rng[1]]
        hi = [d for d in data if sel(d) and d["sec"] is not None and hi_rng[0] <= d["sec"] <= hi_rng[1]]
        if len(lo) < 5 or len(hi) < 5:
            print("  %-24s 样本不足（%s: %d ；%s: %d），待积累"
                  % (label, lo_rng, len(lo), hi_rng, len(hi)))
            return
        parts = []
        for key, nm in (("opp", "对手强度"), ("net", "我方分/房")):
            m1 = st.mean([d[key] for d in lo]); m2 = st.mean([d[key] for d in hi])
            se = math.sqrt(st.pstdev([d[key] for d in lo]) ** 2 / len(lo)
                           + st.pstdev([d[key] for d in hi]) ** 2 / len(hi))
            d_ = m2 - m1
            parts.append("%s Δ=%+.1f (t=%+.2f)" % (nm, d_, (d_ / se if se else 0)))
        print("  %-24s n=%d vs %d | %s" % (label, len(lo), len(hi), " ; ".join(parts)))

    print("A) **增量对照（同臂内 = 正确口径）**：%d-%d 秒 vs %d-%d 秒" % (50, a.lo, a.hi, 59))
    if a.within:
        contrast(lambda d: d.get("st") == a.within, a.within, (50, a.lo), (a.hi, 59))
    else:
        contrast(lambda d: True, "(未限定臂)", (50, a.lo), (a.hi, 59))
    print("B) 参考对照（**按臂 + 同期窗口 since=%s**）：speedtugc(立即) vs speedtugc_w50(等待)" % (a.since or "全时段"))
    for arm in ("speedtugc", "speedtugc_w50"):
        v = [d for d in data if d.get("st") == arm and ((not a.since) or (d.get("ts") or "") >= a.since)]
        if v:
            nopp = len([d for d in v if d["sec"] is not None])
            print("  %-16s n=%d（可定位入席秒 %d） | 对手强度 %+.1f ; 我方分/房 %+.1f"
                  % (arm, len(v), nopp, st.mean([d["opp"] for d in v]), st.mean([d["net"] for d in v])))
    def _ins(d):
        return (not a.since) or (d.get("ts") or "") >= a.since
    aA = [d for d in data if d.get("st") == "speedtugc" and _ins(d)]
    aB = [d for d in data if d.get("st") == "speedtugc_w50" and _ins(d)]
    if len(aA) >= 5 and len(aB) >= 5:
        for key, nm in (("opp", "对手强度"), ("net", "我方分/房")):
            m1 = st.mean([d[key] for d in aA]); m2 = st.mean([d[key] for d in aB])
            se = math.sqrt(st.pstdev([d[key] for d in aA]) ** 2 / len(aA)
                           + st.pstdev([d[key] for d in aB]) ** 2 / len(aB))
            d_ = m2 - m1
            print("    Δ(等待-立即) %s = %+.1f  (t=%+.2f)" % (nm, d_, (d_ / se if se else 0)))
    else:
        print("    （两臂样本不足，待积累）")
    print("  ⚠ A 才是「要不要等更久」的证据；B 只回答「要不要等」。A 不显著时不要据此把全局 wait 从 50 改到 58。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
