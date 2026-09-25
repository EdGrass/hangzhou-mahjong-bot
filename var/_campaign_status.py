# -*- coding: utf-8 -*-
"""`var/_campaign_status.py` —— **役中一屏看板**（一条命令，只读，低优先级）。

## 为什么

役中要看的东西已经分成几把独立的尺子（每轮我都得分别跑）：
`_verdict_watch`（进度）/ `_gate2`（三口径判决读数）/ `_verdict_by_elite`（**强手房**分层）/
`_advance_from_common_origin --by-arm`（**同状态推进率**）/ `_mech_gate`（**改动率**）。
本工具把它们**串成一条命令**，输出一屏，省掉反复手敲、也避免漏看某一项。

## 用法

    python -X utf8 var/_campaign_status.py                       # 默认役 2（c151 vs speedvalue）
    python -X utf8 var/_campaign_status.py --since "<役起点>" --arms speedvalue,speedvaluebc --mech-base speedvalue --mech-cand speedvaluebc
"""
from __future__ import annotations
import argparse, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(args, keep=14, title=""):
    print("\n" + "=" * 92)
    print("▶ %s" % title)
    print("-" * 92)
    try:
        r = subprocess.run([PY, "-X", "utf8"] + args, cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=1800)
        out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    except Exception as e:
        print("  （运行失败：%s）" % e)
        return
    for ln in out[-keep:]:
        print("  " + ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役2")
    ap.add_argument("--since", default="2026-09-23 03:13:44")
    ap.add_argument("--baseline", default="speedc151")
    ap.add_argument("--candidate", default="speedvalue")
    ap.add_argument("--mechanism", default="pairs")
    ap.add_argument("--mech-base", default="speedvalue")
    ap.add_argument("--mech-cand", default="speedvaluebc")
    a = ap.parse_args()

    try:
        from _lowprio_run import lower_self
        print("[campaign_status] %s" % lower_self())
    except Exception:
        pass

    run([os.path.join("var", "_verdict_watch.py"), "--label", a.label, "--since", a.since,
         "--baseline", a.baseline, "--candidate", a.candidate, "--mechanism", a.mechanism,
         "--check-only"], keep=3, title="① 进度（每臂 ≥80 房才判决）")
    run([os.path.join("var", "_gate2.py"), "--since", a.since, "--baseline", a.baseline,
         "--candidate", a.candidate, "--mechanism", a.mechanism, "--min-rooms", "80"],
        keep=18, title="② 三口径判词读数（未达 80/臂 时仅供趋势）")
    run([os.path.join("var", "_verdict_by_elite.py"), "--since", a.since,
         "--arms", "%s,%s" % (a.baseline, a.candidate)], keep=14,
        title="③ 强手房分层（正式赛对手密度对应这一列）")
    run([os.path.join("var", "_advance_from_common_origin.py"), "--rooms", "120", "--k0", "4",
         "--k1", "7", "--since", a.since, "--by-arm"], keep=14,
        title="④ 同状态推进率（k4 向听 → k7 是否听牌，按臂）")
    run([os.path.join("var", "_mech_gate.py"), "--since", a.since, "--base", a.mech_base,
         "--cand", a.mech_cand, "--phase", "draw", "--files", "40", "--river-lo", "16",
         "--river-hi", "32"], keep=10, title="⑤ 下一役候选的机制读数（改动率，全局+中盘切片）")
    print("\n（提示：① 未达 80/臂时，②③④ 都是趋势读数，不作判决；⑤ 用来盯「下一役的臂是否真的在改」。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
