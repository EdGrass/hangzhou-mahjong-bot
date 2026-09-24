# -*- coding: utf-8 -*-
"""`var/_campaign_ready.py` —— **役次起役前的"就绪体检"一条命令**（只读，R1212）。

## 为什么

役次一道接一道（到 10/7 还有 ~5 役），每役的起役前置已经散落成若干条纪律：
预登记文件、臂注册/可实例化/模型在场、足迹体检过、冒烟过、单测过、切换脚本能拦住"在打"、
判决看护在跑、回放看护覆盖 100%。**手工逐条核太容易漏**（本会话就漏过：分支臂足迹没测、切换脚本看不见在打）。

本脚本把"**起役前必须为真**"的项一次性列出来，**任一项不过就明确报错**。

## 用法

    python -X utf8 var/_campaign_ready.py --arms speedvaluebc,speedvaluemeld,speedvaluerank
    python -X utf8 var/_campaign_ready.py --arms speedvaluebc --prereg docs/iter/reports/prereg-campaign3-speedvaluebc-20260924.md
"""
from __future__ import annotations
import argparse, glob, io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def check_arm(name):
    """臂：已注册 / 可实例化 / 模型在场（有 .model/._mnet/.ranker 就断言非 None）。"""
    from run_bot import STRATEGY_FACTORIES as F
    if name not in F:
        return False, "未注册"
    try:
        p = F[name]()
    except Exception as e:
        return False, "实例化失败：%s" % e
    for attr in ("model", "_mnet", "ranker"):
        if hasattr(p, attr) and getattr(p, attr) is None:
            return False, "%s 未加载（缺文件 ⇒ 会退化成 no-op）" % attr
    return True, "ok"


def check_tests(name):
    """找 tests/test_<arm>.py 是否存在（不强跑，跑全量由调用方决定）。"""
    hits = glob.glob(os.path.join(ROOT, "tests", "test_%s*.py" % name))
    return (True, os.path.basename(hits[0])) if hits else (False, "缺单测文件")


def check_replay_coverage(since):
    """本役房间的复盘覆盖（1 房 = 10 gid）。"""
    have = {}
    for p in glob.glob(os.path.join(ROOT, "var", "replays", "recent", "*.json")):
        b = os.path.basename(p)[:-5]
        if "_r" in b:
            have[b.split("_r")[0]] = have.get(b.split("_r")[0], 0) + 1
    tot = cov = 0
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") == "finished" and (d.get("ts") or "") >= since:
            tot += 1
            if have.get(d.get("room"), 0) >= 10:
                cov += 1
    return (cov / tot if tot else 1.0), cov, tot


def check_guide_smoke():
    """★ 跑一次 `run_bot.py --smoke`：指南版本自检若报 BREAKING ⇒ 返回 (False, 摘要)。

    为什么放进"就绪体检"：平台随时可能发 BREAKING（v35 就是这样，2026-09-23 发布、
    当天就让 10 次 `TOURNAMENT_GONE` 被我们误判成"房已删"而退出）。起役前必须看到这个红灯。
    """
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "run_bot.py"), "--smoke"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, "smoke 运行失败：%s" % e
    ok = ("全部通过" in out) and (r.returncode == 0)
    if ok:
        return True, "冒烟全过（含指南版本自检）"
    bad = [x.strip() for x in out.splitlines() if "✗" in x or "BREAKING" in x]
    return False, (bad[0][:160] if bad else "冒烟存在失败项（详见 run_bot.py --smoke）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="逗号分隔的候选臂（要检查的）")
    ap.add_argument("--prereg", action="append", default=[], help="预登记文件路径（可多次传）")
    ap.add_argument("--since", default="", help="本役起始时间（检查回放覆盖用）")
    a = ap.parse_args()

    bad = []
    print("=" * 84)
    print("役次起役前就绪体检")
    print("=" * 84)
    print("[1] 臂（注册 / 可实例化 / 模型在场 / 有单测）")
    for name in [x.strip() for x in a.arms.split(",") if x.strip()]:
        ok, msg = check_arm(name)
        t_ok, t_msg = check_tests(name)
        print("    %-20s %s %s | 单测 %s" % (name, "✅" if ok else "❌", msg, t_msg if t_ok else "❌ " + t_msg))
        if not ok:
            bad.append("臂 %s：%s" % (name, msg))
        if not t_ok:
            bad.append("臂 %s：%s" % (name, t_msg))

    print("[2] 预登记文件")
    if not a.prereg:
        print("    （未指定；建议显式传 --prereg）")
    for f in a.prereg:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        ok = os.path.exists(p)
        print("    %-70s %s" % (os.path.basename(p), "✅" if ok else "❌ 不存在"))
        if not ok:
            bad.append("缺预登记：%s" % f)

    if a.since:
        print("[3] 本役复盘覆盖（1 房 = 10 gid）")
        cov, c, t = check_replay_coverage(a.since)
        print("    %d/%d = %.1f%%  %s" % (c, t, 100 * cov, "✅" if cov >= 0.70 else "❌ (<70%)"))
        if cov < 0.70:
            bad.append("复盘覆盖 %.1f%% < 70%%" % (100 * cov))
    else:
        print("[3] （未传 --since ⇒ 跳过复盘覆盖检查）")

    print("[4] 切换脚本的在打对局闸门")
    try:
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _switch_campaign as sw
        procs = sw.inflight_process()
        print("    %s" % ("✅ 当前无在打对局" if not procs else "⏳ 有在打：%s（切换时会被拦住，属正常）" % (procs,)))
    except Exception as e:
        print("    ❌ 无法加载 _switch_campaign：%s" % e)
        bad.append("切换脚本不可用")

    print("[5] 指南版本 / 冒烟自检（run_bot.py --smoke）")
    s_ok, s_msg = check_guide_smoke()
    print("    %s %s" % ("✅" if s_ok else "❌", s_msg))
    if not s_ok:
        bad.append("指南版本/冒烟：%s" % s_msg)

    print()
    if bad:
        print("❌ 未就绪 %d 项：" % len(bad))
        for b in bad:
            print("   - " + b)
        return 2
    print("✅ 全部就绪（可起役）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
