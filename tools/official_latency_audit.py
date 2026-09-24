# -*- coding: utf-8 -*-
"""官方赛决策延迟审计：扫 run_bot 录制的 dec 文件与 official log。

用途：二测/正式赛后回答“M=10 实际有多少出牌 >3s、多少响应 >1s、预热是否生效、有多少 409/超窗”。
只读，不修改任何状态。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def percentile(xs, p):
    if not xs:
        return 0.0
    ys = sorted(float(x) for x in xs)
    i = max(0, min(len(ys) - 1, int(math.ceil(float(p) * len(ys))) - 1))
    return ys[i]


def _summary(xs, limit_ms):
    return {
        "n": len(xs),
        "p50": percentile(xs, 0.50),
        "p95": percentile(xs, 0.95),
        "p99": percentile(xs, 0.99),
        "max": max(xs) if xs else 0.0,
        "over_limit": sum(1 for x in xs if float(x) > limit_ms),
        "over_3000": sum(1 for x in xs if float(x) > 3000.0),
        "over_1000": sum(1 for x in xs if float(x) > 1000.0),
    }


def audit_dec_records(records):
    draw, response = [], []
    for r in records:
        if not isinstance(r, dict) or r.get("k") != "d":
            continue
        ms = r.get("ms")
        if ms is None:
            continue
        phase = str(r.get("p") or "")
        try:
            val = float(ms)
        except Exception:
            continue
        if phase == "draw":
            draw.append(val)
        elif phase.startswith("response_"):
            response.append(val)
    return {"draw": _summary(draw, 3000.0),
            "response": _summary(response, 1000.0)}


def audit_log_lines(lines):
    out = {"warmup_ok": 0, "http_409": 0, "timeout": 0}
    for line in lines:
        s = str(line).lower()
        if "预热完成" in line or "warmup=" in s:
            out["warmup_ok"] += 1
        if "409" in s:
            out["http_409"] += 1
        if any(k in s for k in ("timeout", "超窗口", "超窗", "丢窗口")):
            out["timeout"] += 1
    return out


def load_dec_records(paths):
    out = []
    for path in paths:
        try:
            fh = io.open(path, encoding="utf-8")
        except OSError:
            continue
        try:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
        finally:
            try:
                fh.close()
            except Exception:
                pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="var/replays/official_1024_*",
                    help="官方录制目录 glob（默认 var/replays/official_1024_*）")
    ap.add_argument("--logs", default="logs/official_1024_*.log",
                    help="官方日志 glob（默认 logs/official_1024_*.log）")
    ap.add_argument("--lowprio", action="store_true", help="自降优先级")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args(argv)

    if a.lowprio:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from _lowprio import lower
            lower(idle=True)
        except Exception:
            pass

    dec_files = []
    for d in glob.glob(os.path.join(ROOT, a.dirs)):
        dec_files += glob.glob(os.path.join(d, "*.jsonl"))
    log_files = glob.glob(os.path.join(ROOT, a.logs))
    recs = load_dec_records(dec_files)
    lat = audit_dec_records(recs)
    log_lines = []
    for path in log_files:
        try:
            log_lines += io.open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            pass
    logs = audit_log_lines(log_lines)
    result = {"dec_files": len(dec_files), "records": len(recs),
              "logs": len(log_files), "latency": lat, "log_counts": logs}
    if a.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if lat["draw"]["n"] or lat["response"]["n"] else 1
    print("官方决策延迟审计")
    print("  dec 文件=%d  决策记录=%d  log 文件=%d" % (len(dec_files), len(recs), len(log_files)))
    for name, limit in (("draw", "3s"), ("response", "1s")):
        x = lat[name]
        print("  %-8s n=%d p50=%.1fms p95=%.1fms p99=%.1fms max=%.1fms  >%s=%d" % (
            name, x["n"], x["p50"], x["p95"], x["p99"], x["max"], limit, x["over_limit"]))
    print("  log: warmup=%d  409=%d  timeout/超窗=%d" % (
        logs["warmup_ok"], logs["http_409"], logs["timeout"]))
    ok = (lat["draw"]["n"] + lat["response"]["n"]) > 0
    print("  结论: %s" % ("有数据 ✓" if ok else "没有找到官方 dec 记录（检查 --dirs/录制是否开启）"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
