# -*- coding: utf-8 -*-
"""给 ab_readout 加"对手强度"与"桌强调整后的净胜"（2026-09-16，回答"为什么又掉分"的副产品）。

动机（2026-09-16 实测）：我们 142 个"强桌"房 −26.3/房、135 个"弱桌"房 +32.8/房（差 ~59 分/房）。
⇒ 若两臂的桌强分布不同，**净胜/房 会把"桌差"读成"策略差"**。这里做两件事：
  ① 逐房算**因果**对手强度（只用该房**之前**的历史，避免看未来；只算 ≥8 房的玩家）；
  ② 用全样本回归斜率把各臂的净胜调整到"共同桌强"上 ⇒ 输出"调整后净胜/房"。
"""
import io
import json

ME = "u_7a3fba48d70b"


def load_rows(path):
    rows = []
    for ln in io.open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    return rows


def opponent_strength(rows, min_rooms=8):
    """room -> 该房三个对手的**因果**平均强度（分/房）。只统计此刻历史房数 ≥ min_rooms 的对手。"""
    prefix = {}
    out = {}
    for d in sorted([r for r in rows if r.get("room")], key=lambda r: r.get("ts") or ""):
        rk = d.get("ranking") or []
        if not any(x.get("user_id") == ME for x in rk):
            continue
        vals = []
        for x in rk:
            if x.get("user_id") == ME:
                continue
            s = prefix.get(x.get("user_id"))
            if s and s[1] >= min_rooms:
                vals.append(s[0] / s[1])
        if vals:
            out[d["room"]] = sum(vals) / len(vals)
        for x in rk:                     # 本房计入历史（供之后的房使用）
            try:
                sc = float(x.get("total_score"))
            except Exception:
                continue
            s = prefix.setdefault(x.get("user_id"), [0.0, 0])
            s[0] += sc
            s[1] += 1
    return out


def slope(xs, ys):
    """最小二乘斜率（x=对手强度, y=净胜）。"""
    if len(xs) < 3:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
