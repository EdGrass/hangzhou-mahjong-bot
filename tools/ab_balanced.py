"""tools/ab_balanced —— 半程换座对（crossover）A/B 的合并裁决（P2b/P4 工具）。

背景（health-audit-2026-09-08）：同策略混配下绝对座对/占位效应达 ±5-11/场，
单形态 A/B（候选固定某座对）不可信。规范实验 = 两个半程：
  half1: 候选在座对 P（如 青龙/白虎），基准 Q（朱雀/玄武）→ δ1
  half2: 换座：候选在 Q，基准 P → δ2
模型：δ1 = T + b，δ2 = T − b（b = P 座对的常数偏倚；可先从 E×4 标定验证）。
  → 真效应 T = (δ1 + δ2)/2；座偏 b = (δ1 − δ2)/2。

用法（half 内角色由 --roles JSON 或日志内策略标签自动判定）：
  python tools/ab_balanced.py \
      --half1 "logs/e4x1_*.log"  --half2 "logs/e4x2_*.log" \
      --roles1 '{"qinglong":"A","baihu":"A","zhuque":"B","xuanwu":"B"}' \
      --roles2 '{"qinglong":"B","baihu":"B","zhuque":"A","xuanwu":"A"}'
输出：两半各自 n/δ/CI + T（含 CI）+ b。
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os

from session_health import audit, parse_log


def _half(specs, roles):
    out = audit(specs, roles)
    d = out["delta"]
    if not d or d["n"] == 0:
        return None, None
    return d, out


def _stats_of(n, mean, sd):
    if not n:
        return None
    se = sd / math.sqrt(n)
    return {"n": n, "delta": round(mean, 3), "sd": round(sd, 2),
            "se": round(se, 4),
            "ci95": [round(mean - 1.96 * se, 3), round(mean + 1.96 * se, 3)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half1", nargs="+", required=True)
    ap.add_argument("--half2", nargs="+", required=True)
    ap.add_argument("--roles1", default="")
    ap.add_argument("--roles2", default="")
    ap.add_argument("--roles-file1", default="")
    ap.add_argument("--roles-file2", default="")
    args = ap.parse_args()

    def paths_of(globs):
        out = []
        for p in globs:
            out += glob.glob(p) if glob.has_magic(p) else [p]
        return sorted(set(out))

    def roles_of(specs, raw, raw_file):
        if raw_file:
            with open(raw_file, encoding="utf-8") as f:
                raw = f.read()
        if not raw:
            return None
        m = json.loads(raw)
        roles = {}
        for sub, side in m.items():
            for s in specs:
                if sub in s["name"]:
                    roles[s["name"]] = side
        return roles

    p1, p2 = paths_of(args.half1), paths_of(args.half2)
    s1 = [{"name": os.path.basename(p), "path": p} for p in p1]
    s2 = [{"name": os.path.basename(p), "path": p} for p in p2]
    d1, h1 = _half(s1, roles_of(s1, args.roles1, args.roles_file1))
    d2, h2 = _half(s2, roles_of(s2, args.roles2, args.roles_file2))
    res = {"half1": d1, "half2": d2}
    if not d1 or not d2:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 3
    # 合并：T = (δ1+δ2)/2，SE_T = 0.5*sqrt(se1²+se2²)；b = (δ1−δ2)/2
    se_t = 0.5 * math.sqrt(d1["se"] ** 2 + d2["se"] ** 2)
    t = (d1["delta"] + d2["delta"]) / 2
    b = (d1["delta"] - d2["delta"]) / 2
    res["T_estimate"] = {"delta": round(t, 3), "se": round(se_t, 4),
                         "ci95": [round(t - 1.96 * se_t, 3),
                                  round(t + 1.96 * se_t, 3)]}
    res["seat_bias_est"] = round(b, 3)
    res["note"] = ("T=(half1+half2)/2 消座偏；b=(half1-half2)/2 为 P 座对偏倚估计"
                   "（E×4 标定下 T 应≈0 且 b 反映结构偏倚）")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
