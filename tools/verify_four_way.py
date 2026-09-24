# -*- coding: utf-8 -*-
"""**四方一致性核查**（T-1h / 每次换策略后必跑）。

为什么需要（R647 的实测风险）：`.official_spec.json` 的 `strategy` 曾与 `_keeper_strategy.txt` 脱钩
（spec 停在已弃用的 `speedc211`，而 keeper 在跑 `speedtugc`）⇒
**整机重启时 `_ensure_all.py` 会按 spec 拉起一个已弃用的策略**（静默用错策略）⇒ 比赛当天可能白给。

本工具把四处**一次读完并对账**：
  ① `var/.official_spec.json` → `strategy`        （重启路径的上游）
  ② `var/_keeper_strategy.txt`                     （watchdog 恢复 keeper 时的依据）
  ③ 运行中的 keeper argv（若在跑）                 （A/B 模式下 keeper 不存在 ⇒ 改看 ④）
  ④ 运行中的 run_bot / match_super argv            （**真正在打的那个策略**）
并额外报告：是否处于 A/B / official 模式（这两种模式下"运行策略 != 声明策略"是**设计如此**）。

用法：
    python -X utf8 tools/verify_four_way.py            # 人读
    python -X utf8 tools/verify_four_way.py --quiet    # 只输出结论 + 退出码（0=一致 / 2=不一致）
"""
from __future__ import annotations
import argparse, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "var", ".official_spec.json")
KSTRAT = os.path.join(ROOT, "var", "_keeper_strategy.txt")
AB = os.path.join(ROOT, "var", ".ab_mode")
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")


def _argv_strategy(basename):
    """返回运行中的 <basename> 进程的 --strategy 值（可能多个）。"""
    out = []
    try:
        import psutil
    except Exception:
        return out
    for p in psutil.process_iter(["cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            argv = p.info.get("cmdline") or []
            if not any(os.path.basename(str(a).replace("\\", "/")) == basename for a in argv[1:]):
                continue
            for i, a in enumerate(argv):
                if a == "--strategy" and i + 1 < len(argv):
                    out.append(str(argv[i + 1]))
        except Exception:
            pass
    return out


def check(spec=None, kstrat=None, ab=None, official=None, procs=None):
    """返回 (ok, rows, bad, mode)。

    ★ 全部输入可注入（`spec`/`kstrat`/`ab`/`official` 为路径，`procs` 为
    `{"keeper":[...], "match_super":[...], "run_bot":[...]}`），以便单测覆盖各分支。
    """
    spec = spec if spec is not None else SPEC
    kstrat = kstrat if kstrat is not None else KSTRAT
    ab_path = ab if ab is not None else AB
    off_path = official if official is not None else OFFICIAL
    decl = None
    try:
        decl = json.loads(io.open(spec, encoding="utf-8").read()).get("strategy")
    except Exception:
        pass
    kfile = None
    try:
        kfile = io.open(kstrat, encoding="utf-8").read().strip()
    except Exception:
        pass
    if procs is None:
        keeper = _argv_strategy("_keeper.py")
        ms = _argv_strategy("match_super.py")
        rb = _argv_strategy("run_bot.py")
    else:
        keeper = list(procs.get("keeper") or [])
        ms = list(procs.get("match_super") or [])
        rb = list(procs.get("run_bot") or [])
    ab = os.path.exists(ab_path)
    off = os.path.exists(off_path)
    roster = []
    try:
        roster = list(json.loads(io.open(ab_path, encoding="utf-8").read()).get("arms") or [])
    except Exception:
        roster = []
    rows = [("① spec.strategy", decl), ("② _keeper_strategy.txt", kfile),
            ("③ keeper argv", keeper or None), ("④ match_super argv", ms or None),
            ("④ run_bot argv", rb or None)]
    bad = []
    if decl is None or kfile is None:
        bad.append("spec 或策略文件缺失/不可读")
    if decl and kfile and decl != kfile:
        if off:
            # ★ R1338：只有 `.official_mode` 存在时，spec 才是“活的”（`_ensure_all.official_argv()` 只在官方分支里读它）
            #   ⇒ 这才是 R647 的真风险：重启会按 spec 拉起别的策略。
            bad.append("①↔② 不一致（official 模式下就是 R647 的静默风险：重启会按 spec 拉起别的策略）")
        else:
            #   反之（A/B 或常规生产）：无哨兵 ⇒ spec 被任何自愈路径读到的概率为 0
            #   （而 A/B 期间 ② 本来就会**每批轮换**，要求①=② 是不可满足的——旧版会永远挂红，只造成警报疲劳）
            rows.append(("⚠ ①↔②（dormant）",
                         "spec=%s / keeper=%s —— 无 .official_mode，当前**不被任何自愈路径读取**；下次切换会被覆盖" % (decl, kfile)))
    if off:
        # 官方模式：keepalive 直接 run_bot，不经 keeper；以 run_bot 的实际策略为准
        for v in set(rb):
            if decl and v != decl:
                bad.append("官方模式下 run_bot 策略 %s != spec %s" % (v, decl))
    elif ab:
        # A/B 模式：keeper 不存在是设计如此；run_bot 会随轮转变化 ⇒ 只要求 ①↔② 一致（基线），
        # 外加：**在跑的臂必须属于本役 roster**（防"陈旧/错误臂还在打"）。
        if roster:
            for v in set(rb) | set(ms):
                if v not in roster:
                    bad.append("在跑的臂 %s 不属于本役 roster %s" % (v, roster))
    else:
        for v in set(keeper):
            if decl and v != decl:
                bad.append("keeper 在跑 %s，但 spec 声明 %s" % (v, decl))
        for v in set(rb):
            if decl and v != decl:
                bad.append("run_bot 在跑 %s，但 spec 声明 %s" % (v, decl))
    return (not bad), rows, bad, {"ab": ab, "official": off}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    ok, rows, bad, mode = check()
    rows_roster = []
    rows_running = []
    try:
        rows_roster = list(json.loads(io.open(AB, encoding="utf-8").read()).get("arms") or [])
        rows_running = sorted(set(x for k, v in rows if k.startswith("④") for x in (v or [])))
    except Exception:
        pass
    if not a.quiet:
        print("=== 四方一致性核查 ===")
        for k, v in rows:
            print("  %-24s %s" % (k, v if v is not None else "（不在跑 / 不存在）"))
        print("  模式：%s" % ("官方赛" if mode["official"] else ("A/B 轮转" if mode["ab"] else "常规生产")))
        if mode["ab"]:
            print("  ⚠ A/B 模式：keeper 不存在是**设计如此**；② 本身会每批轮换 ⇒ ①↔② 在此模式下**是 dormant 不阻塞**；只有 `.official_mode` 存在时才硬要求一致（R1338）")
            print("  本役 roster：%s；当前在跑：%s" % (rows_roster, rows_running))
        print()
    if bad:
        print("FAIL：")
        for b in bad:
            print("  - %s" % b)
        return 2
    print("OK：四方一致（spec=%s）" % rows[0][1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
