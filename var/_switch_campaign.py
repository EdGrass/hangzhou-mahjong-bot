# -*- coding: utf-8 -*-
"""`var/_switch_campaign.py` —— **役次切换的安全封装**（默认 dry-run；`--go` 才真切换）。

## 为什么（R1204）

到 10/7 前还要切换 ~5 次役（每次都是"停当前役 → 起下一役"）。历史上这类手工切换踩过三个坑：

1. **漏 `--bundles=`** ⇒ 判据阈值会**悄悄**从 1.50 变成 1.96（R1156）；
2. **忘 `--started=`** ⇒ 台账把上一役的房算进新役；
3. **臂依赖模型文件但文件缺失** ⇒ 臂静默退化成 no-op，**整役白跑**（R1191 立的前置断言）。

本脚本把这三条**固化成前置检查**。

## 行为

- **默认 dry-run**：只做检查并打印将执行的命令，**不动 A/B**；
- `--go`：检查全过后执行 `ab_ctl.py stop` → `start <baseline>,<candidate> 1 --bundles=<baseline> --started=<now>`；
- **任一检查不过即中止**（不执行任何动作）。

用法：
    python -X utf8 var/_switch_campaign.py --baseline speedvalue --candidate speedvaluebc
    python -X utf8 var/_switch_campaign.py --baseline speedvalue --candidate speedvaluebc --go
"""
from __future__ import annotations
import argparse, datetime as dt, io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")


def check_arms(base, *cands):
    """两臂可实例化 + 模型在场（有 .model / ._mnet 就断言非 None）。"""
    from run_bot import STRATEGY_FACTORIES as F
    out = []
    for name in (base,) + tuple(cands):
        if name not in F:
            out.append("臂未注册：%s" % name)
            continue
        try:
            p = F[name]()
        except Exception as e:
            out.append("实例化失败：%s（%s）" % (name, e))
            continue
        for attr, label in (("model", "模型"), ("_mnet", "副露网")):
            if hasattr(p, attr) and getattr(p, attr) is None:
                out.append("%s 的%s 未加载（缺文件 ⇒ 臂会退化成 no-op）" % (name, label))
    return out


def inflight_rooms(max_age_min=40):
    """台账里 status != finished **且** 时间戳在最近 `max_age_min` 分钟内的房 ⇒ 真的在打，必须等它自然结束。

    ⚠ 台账里有**历史残留**（如 9/10、9/16、9/22 的 `running` 行——那些房早已被服务端清理、不会再结束）。
    若不加时间窗，切换检查会被这些僵尸行**永久挡住**（R1204 实测：3 条残留行把 dry-run 判死）。
    返回 (inflight, stale) 两个列表：前者阻塞切换，后者只在报告里提示。
    """
    bad, stale = [], []
    if not os.path.exists(LEDGER):
        return bad, stale
    now = dt.datetime.now()
    for ln in io.open(LEDGER, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") == "finished":
            continue
        ts = d.get("ts") or ""
        try:
            age = (now - dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60.0
        except Exception:
            age = 1e9
        rec = (d.get("room"), d.get("strategy"), d.get("status"), ts)
        (bad if age <= max_age_min else stale).append(rec)
    return bad, stale


def inflight_process():
    """★ 从**进程表**找正在打的房（台账要等房结束才落行 ⇒ 只看台账会漏掉"正在打"）。

    判据：python 进程 argv 的**基名**里有 `run_bot.py`，并从 argv 里取 `a_*` 房号与 `--strategy` 的值。
    返回 [(pid, room, strategy)]；**非空即拒绝切换**（红线：绝不在对局进行中强停）。
    """
    out = []
    try:
        import psutil
    except Exception:
        return out
    for pr in psutil.process_iter(["cmdline"]):
        try:
            argv = [str(x) for x in (pr.info.get("cmdline") or [])]
            base = [os.path.basename(a.replace("\\", "/")).lower() for a in argv]
            if "run_bot.py" not in base:
                continue
            room = next((a for a in argv if a.startswith("a_")), "?")
            strat = ""
            for i, a in enumerate(argv):
                if a == "--strategy" and i + 1 < len(argv):
                    strat = argv[i + 1]
            out.append((pr.pid, room, strat))
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", default="", help="（2 臂兼容）候选臂")
    ap.add_argument("--candidates", default="",
                    help="（N 臂）候选臂，逗号分隔；与 --candidate 二选一（R1264 支持 3 臂役）")
    ap.add_argument("--bundles", default="", help="判据 bundle（默认=baseline；建议显式传，见 R1156）")
    ap.add_argument("--go", action="store_true", help="真的执行切换（默认只 dry-run）")
    a = ap.parse_args()

    cands = [x.strip() for x in a.candidates.split(",") if x.strip()]
    if not cands and a.candidate.strip():
        cands = [a.candidate.strip()]
    if not cands:
        ap.error("需要 --candidate（2 臂）或 --candidates（N 臂，逗号分隔）")
    bundles = a.bundles or a.baseline
    started = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    problems = list(check_arms(a.baseline, *cands))
    infl, stale = inflight_rooms()
    if infl:
        problems.append("台账里有 %d 个在打/未完结房（切换前请等其自然结束）：%s" % (len(infl), infl[:3]))
    procs = inflight_process()
    if procs:
        problems.append("★ 进程表里检测到**正在打的对局**：%s ⇒ 必须等它自然结束（红线：不强停）"
                        % ", ".join("pid=%s room=%s arm=%s" % t for t in procs))

    print("=== 役次切换检查（%s → %s）===" % (a.baseline, ",".join(cands)))
    print("  判据 bundle   ：%s（%s）" % (bundles, "默认=baseline" if not a.bundles else "显式指定 ✓"))
    print("  起役时间戳    ：%s" % started)
    if stale:
        print("  台账残留（**不影响切换**；台账只追加、役中不动 ⇒ 仅记录，不要手改）：%d 条 %s" % (len(stale), stale[:2]))
    if problems:
        print("  检查未通过：")
        for p in problems:
            print("     - " + p)
        print("  ⇒ 中止（未执行任何动作）")
        return 2

    py = sys.executable
    stop_cmd = [py, "-X", "utf8", os.path.join(ROOT, "tools", "ab_ctl.py"), "stop"]
    start_cmd = [py, "-X", "utf8", os.path.join(ROOT, "tools", "ab_ctl.py"), "start",
                 ",".join([a.baseline] + cands), "1", "--bundles=%s" % bundles,
                 "--started=%s" % started]
    print("  检查全过")
    print("  将执行：")
    print("    1) " + " ".join(stop_cmd[1:]))
    print("    2) " + " ".join(start_cmd[1:]))
    if not a.go:
        print("  （dry-run：未执行；加 --go 才真的切换）")
        return 0
    for cmd in (stop_cmd, start_cmd):
        print("  → 执行 " + " ".join(cmd[1:]), flush=True)
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            print("  返回码 %d ⇒ 中止后续步骤" % r.returncode)
            return r.returncode
    print("  切换完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
