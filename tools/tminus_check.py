# -*- coding: utf-8 -*-
"""`tminus_check` —— 开赛前的**只读**体检一台（给 17:00 提醒用，一条命令看全）。

它把本会话验证过的赛前项目打包成一张表（**不写任何状态、不动进程**）：
  ① `tools/preflight.py`（引擎/延迟/自愈链）② `tools/rules_guard.py`（YouCaiBiKao ↔ 策略）
  ③ `/ready` 状态与门户赛事（报名/截止/开赛/我已报名）④ 本役 A/B 数据完整性（`tools/ab_integrity.py`）
  ⑤ 榜单快照（`tools/ladder_snapshot.py --show`）⑥ 进程清单与"有无 keeper 残留"

用法：
    python -X utf8 tools/tminus_check.py                       # 用默认二测令牌/策略
    python -X utf8 tools/tminus_check.py --strategy speedtugc --token-file var/.token_1024_20260917
"""
from __future__ import annotations
import argparse, datetime as dt, io, json, os, ssl, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("HM_SERVER", "").strip() or "http://127.0.0.1:8080"


def run(cmd, timeout=180):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def portal(path, cookie):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(BASE + path, headers={"Cookie": cookie})
    return json.loads(urllib.request.urlopen(req, timeout=20, context=ctx).read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="speedtugc")
    ap.add_argument("--token-file", default="var/.token_1024_20260917")
    ap.add_argument("--tid", default="")
    ap.add_argument("--since", default="",
                    help="显式 A/B 战役窗口（无 .ab_mode 暂停期用）")
    ap.add_argument("--arms", default="",
                    help="逗号分隔的 A/B 臂列表；与 --since 一起传给 ab_integrity")
    a = ap.parse_args()
    rows = []

    def add(name, ok, detail):
        rows.append((("✅" if ok is True else ("⚠️" if ok is None else "❌")), name, detail))

    # ① preflight
    rc, out = run([sys.executable, "-X", "utf8", "tools/preflight.py"])
    last = [l for l in out.strip().splitlines() if l.strip()][-1] if out.strip() else ""
    add("preflight", (rc == 0 and "READY" in last), last[:90] or ("rc=%d" % rc))

    # ② rules_guard
    rc, out = run([sys.executable, "-X", "utf8", "tools/rules_guard.py",
                   "--strategy", a.strategy, "--token-file", a.token_file])
    ycbk = None
    for l in out.splitlines():
        if "YouCaiBiKao" in l and "=" in l:
            ycbk = l.strip()[:60]
    add("rules_guard（策略↔规则）", (rc == 0), (ycbk or ("rc=%d" % rc)))

    # ③ /ready + 门户赛事
    try:
        rc, out = run([sys.executable, "-X", "utf8", "var/_ready_1024.py", "--status"])
        add("ready/报名状态", (rc == 0), out.strip().splitlines()[0][:90] if out.strip() else "无输出")
        ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
        j = portal("/portal/api/tournaments", ck)
        t = next((x for x in (j.get("tournaments") or []) if x.get("id") == a.tid), None)
        if t is None:
            add("门户赛事", False, "没找到 %s" % a.tid)
        else:
            f = lambda x: dt.datetime.fromtimestamp(int(x)).strftime("%m-%d %H:%M") if x else "-"
            now = dt.datetime.now()
            start = dt.datetime.fromtimestamp(int(t.get("start_at"))) if t.get("start_at") else None
            hrs = ((start - now).total_seconds() / 3600.0) if start else None
            add("门户赛事", bool(t.get("my_registered")),
                "%s status=%s 报名截止=%s 开赛=%s 距开赛=%.1fh 已报名=%s 我已报名=%s" % (
                    t.get("name"), t.get("status"), f(t.get("register_deadline")), f(t.get("start_at")),
                    (hrs if hrs is not None else -1), t.get("registered"), t.get("my_registered")))
    except Exception as e:
        add("门户/ready", False, repr(e)[:80])

    # ④ A/B 完整性：无 .ab_mode 的暂停期可用 --since/--arms 显式指定战役窗口，
    #    否则历史上已归档的旧异常会被误判为“本役异常”并阻止开赛切换。
    integrity_cmd = [sys.executable, "-X", "utf8", "tools/ab_integrity.py"]
    if a.since:
        integrity_cmd += ["--since", a.since]
    if a.arms:
        integrity_cmd += ["--arms", a.arms]
    rc, out = run(integrity_cmd)
    add("本役数据完整性", (rc == 0), (out.strip().splitlines()[-1][:90] if out.strip() else ""))

    # ⑤ 榜单
    rc, out = run([sys.executable, "-X", "utf8", "tools/ladder_snapshot.py", "--show"])
    line = next((l for l in out.splitlines() if l.strip().startswith("[all]")), "")
    add("榜单(all)", (rc == 0), line.strip()[:90])

    # ⑥ 进程
    try:
        import psutil
        names = []
        for p in psutil.process_iter(["cmdline", "exe"]):
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            for x in (p.info.get("cmdline") or [])[1:]:
                b = os.path.basename(str(x).replace("\\", "/")).lower()
                if b in ("_keeper.py", "_ab_driver.py", "match_super.py", "run_bot.py",
                         "_official_keepalive.py", "_watchdog.py"):
                    names.append(b)
                    break
        cnt = {n: names.count(n) for n in sorted(set(names))}
        add("进程", (cnt.get("_keeper.py", 0) == 0 or cnt.get("_official_keepalive.py", 0) == 0), str(cnt))
    except Exception as e:
        add("进程", None, "psutil 不可用：%s" % e)

    print("=" * 92)
    print("赛前只读体检（tminus_check）  %s   策略=%s 令牌=%s" % (
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a.strategy, a.token_file))
    print("-" * 92)
    for mark, name, detail in rows:
        print("%s %-22s %s" % (mark, name, detail))
    bad = sum(1 for m, _, _ in rows if m == "❌")
    warn = sum(1 for m, _, _ in rows if m == "⚠️")
    print("-" * 92)
    print("结论：%s（❌ %d / ⚠️ %d）" % ("可以按操作单执行" if not bad else "**有硬失败，先处理**", bad, warn))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
