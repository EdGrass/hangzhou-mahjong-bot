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
import argparse, io, json, os, subprocess, sys   # ★ R1577：新增 io/json（ab_defaults 要用）

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


def ab_defaults(path=None):
    """★ R1577：默认值必须取自**当前在跑的役**（`var/.ab_mode`）。

    为什么：旧实现把 `--since/--baseline/--candidate` 默认**写死成役2**
    （`2026-09-23 03:13:44` / `speedc151` vs `speedvalue`）⇒ 无参跑（而 HANDOFF 的“一屏总览”就叫人这么跑）
    会打印役2 的“✅ 可判决 / ★ 判定：ADOPT speedvalue” ⇒ 读者以为**当前役**已有结论。
    现在：从 `.ab_mode` 取（支持 N 臂）；取不到 ⇒ 返 None，调用方**显式告诉读者这是回退**。
    """
    p = path or os.path.join(ROOT, "var", ".ab_mode")
    try:
        cfg = json.loads(io.open(p, encoding="utf-8-sig").read())
    except Exception:
        return None
    if isinstance(cfg.get("arms"), list):
        arms = [str(x) for x in cfg["arms"] if x]
    else:
        arms = [str(x) for x in (cfg.get("a"), cfg.get("b")) if x]
    if not arms:
        return None
    base = str((cfg.get("bundles") or arms[:1])[0])
    cands = [x for x in arms if x != base]
    if not cands:
        return None
    return {"since": str(cfg.get("started") or ""), "baseline": base,
            "candidates": cands, "arms": [base] + cands}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役中")
    ap.add_argument("--since", default="", help="空 ⇒ 从 .ab_mode.started 取")
    ap.add_argument("--baseline", default="", help="空 ⇒ 从 .ab_mode.bundles[0] 取")
    ap.add_argument("--candidate", default="", help="空 ⇒ 取第一个非基线臂")
    ap.add_argument("--mechanism", default="pairs")
    ap.add_argument("--mech-base", default="")
    ap.add_argument("--mech-cand", default="")
    a = ap.parse_args()

    d = ab_defaults()
    if d:
        print("[campaign_status] 当前役：arms=%s  started=%s（取自 var/.ab_mode）"
              % (",".join(d["arms"]), d["since"] or "?"))
        a.since = a.since or d["since"]
        a.baseline = a.baseline or d["baseline"]
        a.candidate = a.candidate or d["candidates"][0]
        a.mech_base = a.mech_base or d["baseline"]
        a.mech_cand = a.mech_cand or d["candidates"][0]
    else:
        print("[campaign_status] ⚠ 读不到 var/.ab_mode ⇒ **回退到写死的役2**"
              "（2026-09-23 03:13:44 / speedc151 vs speedvalue）：它**不是当前役**，"
              "请显式传 --since/--baseline/--candidate（或先确认役是否已收口）。")
        a.since = a.since or "2026-09-23 03:13:44"
        a.baseline = a.baseline or "speedc151"
        a.candidate = a.candidate or "speedvalue"
        a.mech_base = a.mech_base or "speedvalue"
        a.mech_cand = a.mech_cand or "speedvaluebc"

    try:
        from _lowprio_run import lower_self
        print("[campaign_status] %s" % lower_self())
    except Exception:
        pass

    cands = list(d["candidates"]) if d else [a.candidate]     # ★ R1577：N 臂逐个看
    for i, cand in enumerate(cands):
        run([os.path.join("var", "_verdict_watch.py"), "--label", "%s%s" % (a.label, cand[:12]),
             "--since", a.since, "--baseline", a.baseline, "--candidate", cand,
             "--mechanism", a.mechanism, "--check-only"], keep=3,
            title=("① 进度（每臂 ≥80 房才判决）" if i == 0 else ""))
        run([os.path.join("var", "_gate2.py"), "--since", a.since, "--baseline", a.baseline,
             "--candidate", cand, "--mechanism", a.mechanism, "--min-rooms", "80"],
            # ★ R1577：`_gate2` 的**主/副端点行在表头** —— `keep=18` 会把它们截掉（而它们正是判词最该看的两行）。
            keep=26, title="② 三口径判词读数 · %s（未达 80/臂 时仅供趋势）" % cand)
    # ★ R1577：三臂时分层表是 3×4 行 ⇒ keep 要够大且**列全部臂**（否则第三臂的行被截掉）
    run([os.path.join("var", "_verdict_by_elite.py"), "--since", a.since,
         "--arms", ",".join([a.baseline] + (list(d["candidates"]) if d else [a.candidate]))], keep=24,
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
