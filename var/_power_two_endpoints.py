# -*- coding: utf-8 -*-
"""**两个判决端点的功率表**（净分 / 第一率）—— 给"每臂跑多少房"提供依据。

动机：
  · `ab_readout.py` 印的 `b − a = … ± …` 里的 `±` 是 **95% CI 半宽**（= 1.96×SE），**不是 SE**；
    `t` 才是 `diff / SE`。本工具把 SE / MDE 都显式算出来，避免再误读。
  · 用户判据是 **"只对比第一率"**，而预登记端点是净分 ⇒ 必须知道两个端点**各自的**分辨率。

口径：
  · 净分端点用房间级 `net`（= 我分 − 其余三家均分，恒等于 4/3 × 原始分/房）；
  · 第一率端点用房间级 `rank==1` 的伯努利量；
  · SD 从**本役实测**（`rooms_for`）估计，并给出全史对照。

用法：
    python -X utf8 var/_power_two_endpoints.py --since "2026-09-20 14:54:07"
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "var"))
try:
    from _lowprio import lower
    lower(idle=True)
except Exception:
    pass

import ab_readout as AR                      # noqa: E402

T_CRIT = 1.5


def _mde(sd, n, t=T_CRIT):
    return t * sd * math.sqrt(2.0 / n)


def arms_from_cfg(cfg):
    """★ R1482：从 `.ab_mode` 推 (base, cand)。N 臂优先 `arms`，兼容 `a`/`b`。

    为什么要单独抽出来：旧默认是**写死**的 `speedtugc`/`speedc151`，
    而 `_gate_report.py` 只传 `--since` ⇒ 这一步会对着**错的两个臂**算功率（实测 0/0）。
    """
    arms = ([str(x) for x in cfg.get("arms")] if isinstance(cfg.get("arms"), list)
            else [x for x in (cfg.get("a"), cfg.get("b")) if x])
    base = (cfg.get("bundles") or arms or [""])[0]
    cand = next((x for x in arms if x and x != base), base or "")
    return (base or ""), (cand or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--a", default="")
    ap.add_argument("--b", default="")
    ap.add_argument("--rooms", default="60,100,150")
    a = ap.parse_args()

    # ★ R1482：默认臂改为**从 `.ab_mode` 推**（基线 = bundles[0]，候选 = 第一个非基线臂）。
    #   旧默认是写死的 `speedtugc`/`speedc151` ⇒ `_gate_report.py` 只传 `--since` 时，
    #   这一步会**惄惄对着错的两个臂算功率**（实测输出“数据不足: 0 / 0”）。
    _cfg = {}
    try:
        _cfg = json.load(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8-sig"))
    except Exception:
        _cfg = {}
    _base, _cand = arms_from_cfg(_cfg)
    if not a.a:
        a.a = _base or "speedtugc"
    if not a.b:
        a.b = _cand or "speedc151"
    if not a.since:
        a.since = _cfg.get("started") or "2026-09-20 14:54:07"

    A = AR.rooms_for(a.a, a.since)
    B = AR.rooms_for(a.b, a.since)
    if len(A) < 5 or len(B) < 5:
        print("数据不足: %d / %d" % (len(A), len(B)))
        return 1

    net_a = [r["net"] for r in A]
    net_b = [r["net"] for r in B]
    net_sd = statistics.pstdev(net_a + net_b)
    rank_a = [r["rank"] for r in A]
    rank_b = [r["rank"] for r in B]
    p = (sum(1 for x in rank_a if x == 1) + sum(1 for x in rank_b if x == 1)) / (len(rank_a) + len(rank_b))
    fr_sd = math.sqrt(p * (1 - p))

    d_net = sum(net_b) / len(net_b) - sum(net_a) / len(net_a)
    fa = sum(1 for x in rank_a if x == 1) / len(rank_a)
    fb = sum(1 for x in rank_b if x == 1) / len(rank_b)
    d_fr = 100.0 * (fb - fa)

    se_net = net_sd * math.sqrt(1.0 / len(net_a) + 1.0 / len(net_b))
    se_fr = 100.0 * fr_sd * math.sqrt(1.0 / len(rank_a) + 1.0 / len(rank_b))

    print("端点方差（本役实测）")
    print("  净胜/房  SD = %.1f   （= 原始分/房 SD %.1f × 4/3）" % (net_sd, net_sd * 0.75))
    print("  第一率    p = %.3f    单房 SD = %.1fpp" % (p, 100 * fr_sd))
    allnet = AR.rooms_for(a.a, None)
    print("  [全史 %s 对照] 净胜/房 SD = %.1f" % (a.a, statistics.pstdev([r["net"] for r in allnet])))
    print()
    print("当前读数（n=%d / %d）" % (len(A), len(B)))
    print("  净分   b − a = %+.1f 净胜/房   SE=%.1f   t=%+.2f   （95%%CI 半宽 ≈ %.1f）"
          % (d_net, se_net, d_net / se_net, 1.96 * se_net))
    print("  第一率 b − a = %+.1fpp       SE=%.1fpp z=%+.2f   （95%%CI 半宽 ≈ %.1fpp）"
          % (d_fr, se_fr, d_fr / se_fr, 1.96 * se_fr))
    print()
    print("功率表（t=%.1f 的最小可测差 MDE；并列出「当前效应若为真」的预期 t）" % T_CRIT)
    print("  %-8s %-22s %-22s" % ("房/臂", "净分 MDE(净胜/房)", "第一率 MDE"))
    for n in [int(x) for x in a.rooms.split(",")]:
        m_net = _mde(net_sd, n)
        m_fr = 100.0 * _mde(fr_sd, n)
        t_net = (d_net / (net_sd * math.sqrt(2.0 / n))) if net_sd else 0.0
        t_fr = (d_fr / (100.0 * fr_sd * math.sqrt(2.0 / n))) if fr_sd else 0.0
        print("  %-8d ±%-9.1f (t预期%+.2f)     ±%-6.1fpp (z预期%+.2f)"
              % (n, m_net, t_net, m_fr, t_fr))
    print()
    print("判读：MDE 越小越好；请按『正式赛计分是哪一种』决定以哪个端点为主。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())