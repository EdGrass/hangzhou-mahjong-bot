"""tools/ab_analyze —— A/B 逐场实证分析（games.jsonl 级，σ 校准用）。

history.jsonl 只存批均值；同桌面判定所需的真实方差要从逐场记录算。
用法（给出 combo 子串，如 speedx1x2+speedEx2）：
    python tools/ab_analyze.py speedx1
输出：场数 N、配对差均值 delta、配对差 sd（σ_d）、SE(delta)、95%CI、
逐座每场 sd（σ_seat）、以及按当前均值若要 CI 排除 0 还需多少场。

2026-09-06 C001 实测（8 巡本地）：σ_d≈33.7、σ_seat≈28.9 —— 远大于旧假设 10。
据此 δ=2/场 需 N≈1100+ 局；ab_gate --sigma 应用实证值。
"""
from __future__ import annotations

import json
import math
import sys


def analyze(combo_sub, path="var/arena/games.jsonl"):
    cnt = 0
    dsum = d2 = 0.0
    tsum = t2 = 0.0
    tsamp = 0
    cands = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if combo_sub not in line:
                continue
            r = json.loads(line)
            names = r["seat_names"]
            tot = r["totals"]
            cands |= set(names)
            xs = [tot[i] for i in range(4) if names[i] != "speedE"]
            es = [tot[i] for i in range(4) if names[i] == "speedE"]
            if len(es) != 2 or len(xs) != 2:
                continue
            d = (sum(xs) - sum(es)) / 2.0
            cnt += 1
            dsum += d
            d2 += d * d
            for t in tot:
                tsamp += 1
                tsum += t
                t2 += t * t
    if not cnt:
        return None
    mean = dsum / cnt
    sd_d = math.sqrt(max(d2 / cnt - mean * mean, 0.0))
    se = sd_d / math.sqrt(cnt)
    sd_seat = math.sqrt(max(t2 / tsamp - (tsum / tsamp) ** 2, 0.0))
    ci = (mean - 1.96 * se, mean + 1.96 * se)
    need2 = (1.96 * sd_d / 2.0) ** 2        # 让 ±2 检出（CI 半宽 2 时下界>0）
    return {"games": cnt, "delta": round(mean, 3), "sd_d": round(sd_d, 2),
            "se": round(se, 4), "ci95": [round(ci[0], 3), round(ci[1], 3)],
            "sd_seat": round(sd_seat, 2), "seat_names": sorted(cands),
            "need_games_for_d2": int(math.ceil(need2))}


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/ab_analyze.py <combo子串> [games.jsonl路径]")
        return 2
    sub = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else "var/arena/games.jsonl"
    a = analyze(sub, path)
    if not a:
        print("无数据: %r in %s" % (sub, path))
        return 3
    print("combo≈%s  games=%d  seat_names=%s" % (sub, a["games"], a["seat_names"]))
    print("  delta=%+.3f/场  sd_d=%.2f  SE=%.4f  95%%CI=[%+.2f, %+.2f]"
          % (a["delta"], a["sd_d"], a["se"], a["ci95"][0], a["ci95"][1]))
    print("  sd_seat(逐座每场)=%.2f   按此方差 δ=2/场 需 ~%d 局"
          % (a["sd_seat"], a["need_games_for_d2"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
