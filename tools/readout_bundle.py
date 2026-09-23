# -*- coding: utf-8 -*-
"""readout_bundle —— 把「中期/终点读数」的全套步骤变成**一条命令**并归档。

步骤（与 docs/候选池-下一个月.md 的 checklist 一致）：
  0) 先补拉门户复盘（手动工具，必需；否则机制层覆盖率 0）
  1) ab_readout.py           主判据（净胜/房 + 桌强调整 + top2/名次分）
  2) ab_mech_verdict.py      机制画像 vs 强者参考 + A 级判据（v2 规则）
  3) var/_run_mech.py        零延迟机制层（拆对/对数/听牌/进张遗憾）
  4) var/_own_fan_audit.py   零延迟价值层（胡率/番/爆头）
  5) tools/ab_tenpai.py      逐局听牌速度端点

用法：
  python -X utf8 tools/readout_bundle.py                 # 默认只跑 2~5（不补拉）
  python -X utf8 tools/readout_bundle.py --fetch         # 先补拉 10 房再读（约 10~12 分钟）
输出：控制台 + `var/readouts/readout_<YYYYmmdd_HHMMSS>.txt`（归档，便于事后复核）
"""
from __future__ import annotations
import argparse, datetime as dt, io, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "var", "readouts")


def run(cmd, out):
    out.write("\n" + "=" * 100 + "\n$ " + " ".join(cmd) + "\n" + "=" * 100 + "\n")
    out.flush()
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=3600)
        txt = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        txt = "[timeout]"
    out.write(txt)
    out.flush()
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="窗口起点（默认用 .ab_mode 的 started）")
    ap.add_argument("--fetch", action="store_true", help="先补拉门户复盘（10 房）")
    a = ap.parse_args()
    since = a.since
    if not since:
        try:
            import json
            cfg = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8").read())
            since = cfg.get("started")
        except Exception:
            since = None
    os.makedirs(OUTDIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTDIR, "readout_%s.txt" % ts)
    py = sys.executable
    with io.open(path, "w", encoding="utf-8") as out:
        out.write("读数归档 %s（since=%s）\n" % (ts, since or "-"))
        if a.fetch:
            run([py, "-X", "utf8", "tools/fetch_room_replays.py", "--rooms", "10", "--gap", "1.2"], out)
        run([py, "-X", "utf8", "tools/ab_readout.py"], out)
        if since:
            run([py, "-X", "utf8", "tools/ab_mech_verdict.py", "--since", since], out)
        else:
            run([py, "-X", "utf8", "tools/ab_mech_verdict.py"], out)
        if since:
            run([py, "-X", "utf8", "var/_run_mech.py", "--since", since, "--jobs", "2"], out)
            run([py, "-X", "utf8", "var/_own_fan_audit.py", "--since", since], out)
            run([py, "-X", "utf8", "tools/ab_tenpai.py", "--since", since, "--lowprio"], out)
    print("归档：%s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
