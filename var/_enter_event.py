# -*- coding: utf-8 -*-
"""`var/_enter_event.py` \u2014\u2014 **\u8d5b\u4e8b\u5165\u573a\u4e00\u952e\u5668**\uff08\u9ed8\u8ba4\u53ea\u6253\u5370\u5c06\u505a\u4ec0\u4e48\uff1b`--go` \u624d\u52a8\u624b\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u56db\u6d4b\u5165\u573a\u6642\uff0c\u6211**\u624b\u5de5\u642d\u4e86 10 \u4e2a\u4efb\u52a1**\uff08\u62a5\u540d\u53d6\u4ee4\u724c\u3001/ready\u30013 \u9053\u5207\u6362\u3001T-2min \u4fdd\u9669\u30014 \u9053\u6536\u5c3e\uff09\uff0c
\u8fc7\u7a0b\u4e2d\u8e29\u4e86\u4e24\u4e2a\u81ea\u5df1\u7684\u5751\uff08\u53cc\u53cd\u659c\u6760\u8def\u5f84\u3001ps1 \u8bed\u6cd5\uff09\u3002\u672c\u811a\u672c\u628a\u90a3\u5957\u6d41\u7a0b\u53c2\u6570\u5316\uff0c\u5e76**\u590d\u7528\u4eca\u65e5\u5df2\u9a8c\u8bc1\u7684\u5404\u6ce8\u518c\u811a\u672c**\u3002

\u505a\u4e94\u4ef6\u4e8b\uff1a
  1) \u4ece\u5f53\u524d `.ab_mode` **\u5feb\u7167\u6062\u590d\u4fe1\u606f** \u5230 `var/.resume_spec.json`\uff08\u8d5b\u540e\u539f\u7a97\u53e3/\u539f\u81c2\u6062\u590d\uff09\uff1b
  2) \u95e8\u6237**\u62a5\u540d**\uff08\u672a\u62a5\u540d\u65f6\uff09+ **\u53d6\u4ee4\u724c**\uff08\u4ee4\u724c\u6587\u4ef6\u4e0d\u5b58\u5728\u65f6\uff09+ **POST /ready**\uff1b
  3) \u6309\u5f00\u8d5b\u65f6\u95f4\u7b97\u51fa\u65f6\u95f4\u8868\uff08\u5207\u6362 = \u5f00\u8d5b-40min\uff1b\u91cd\u8bd5 +20min\uff1b\u6700\u540e\u515c\u5e95 +30min\uff1b\u5230\u4f4d\u4fdd\u9669 = \u5f00\u8d5b-5min\uff1b\u6536\u5c3e = \u5f00\u8d5b+3h \u8d77\u6bcf 1.5h \u4e00\u6b21\u00d74\uff09\uff1b
  4) \u7528 `_register_4test_switch.ps1` / `_register_tminus_ready.ps1` / `_register_after_4test.ps1` **\u6ce8\u518c 9 \u4e2a\u4e00\u6b21\u6027\u4efb\u52a1**\uff1b
  5) \u6253\u5370\u5b8c\u6574\u65f6\u95f4\u8868\u4e0e\u9a8c\u8bc1\u6b65\u9aa4\u3002

\u7ea2\u7ebf\uff1a\u4e0d\u5f3a\u505c\u4efb\u4f55\u8fdb\u7a0b\uff1b**\u4e0d\u81ea\u5df1\u8d77\u5f79**\uff08\u53ea\u6ce8\u518c\u4efb\u52a1\uff09\u3002
"""
from __future__ import annotations
import argparse, datetime as dt, io, json, os, ssl, subprocess, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://10.240.169.190:18080"
AB = os.path.join(ROOT, "var", ".ab_mode")
RESUME = os.path.join(ROOT, "var", ".resume_spec.json")
COOKIE = os.path.join(ROOT, "var", ".portal_cookie")


def _ctx():
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
    return c


def get(path, token="", cookie=""):
    hdr = {"Cookie": cookie} if (path.startswith("/portal/") and cookie) else {"Authorization": "Bearer " + token}
    req = urllib.request.Request(BASE + path, headers=hdr)
    with urllib.request.urlopen(req, timeout=25, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def post(path, token="", cookie="", data=b""):
    hdr = {"Cookie": cookie} if (path.startswith("/portal/") and cookie) else {"Authorization": "Bearer " + token}
    req = urllib.request.Request(BASE + path, headers=hdr, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=25, context=_ctx()) as r:
        return r.status, r.read().decode("utf-8", "replace")


def f(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", required=True)
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--strategy", default="")
    ap.add_argument("--prefix", default="HangzhouMajEvent")
    ap.add_argument("--switch-at", default="", help="\u4e0d\u7ed9\u5219 = \u5f00\u8d5b\u65f6\u95f4 - 40min")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    tokfile = a.token_file if os.path.isabs(a.token_file) else os.path.join(ROOT, a.token_file)
    if not a.strategy:
        # ★ R1343：A/B 期间**禁止默认**——`_keeper_strategy.txt` 在 A/B 下是“每批轮换的臂”，
        #   拿它当赛事臂 = 把未经验证的候选臂带上场 ⇒ 必须显式传 --strategy。
        if os.path.exists(AB):
            print("\u274c A/B 正在跑（%s 存在）：_keeper_strategy.txt 会随轮换，"
                  "不能当默认赛事臂 ⇒ 请**显式**传 --strategy <最终要上场的臂>" % AB)
            return 2
        try:
            a.strategy = io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"), encoding="utf-8-sig").read().strip()
        except Exception:
            a.strategy = ""
    if not a.strategy:
        print("\u274c \u65e0\u6cd5\u786e\u5b9a --strategy"); return 2

    # \u2460 \u5feb\u7167\u6062\u590d\u4fe1\u606f
    res = None
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
        arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
        res = {"arms": ",".join([str(x) for x in arms if x]),
               "bundles": ",".join(cfg.get("bundles") or []),
               "started": cfg.get("started") or ""}
    except Exception as e:
        print("\u26a0 \u8bfb .ab_mode \u5931\u8d25\uff08%s\uff09\u21d2 \u8d5b\u540e\u5c06\u56de\u5230\u9ed8\u8ba4\u515c\u5e95" % str(e)[:80])

    # \u2461 \u62a5\u540d / \u4ee4\u724c / ready\uff08\u8ba1\u5212\uff09
    steps = []
    try:
        ck = io.open(COOKIE, encoding="utf-8-sig").read().strip()
        j = get("/portal/api/tournaments", cookie=ck)
        ts = j if isinstance(j, list) else (j.get("tournaments") or [])
        t0 = next((x for x in ts if x.get("id") == a.tid), {})
    except Exception as e:
        t0 = {}; print("\u26a0 \u95e8\u6237\u67e5\u8be2\u5931\u8d25\uff1a%s" % str(e)[:100])
    if t0 and not t0.get("my_registered"):
        steps.append("\u95e8\u6237\u62a5\u540d\uff1aPOST /portal/api/tournaments/%s/register" % a.tid)
    if not os.path.exists(tokfile):
        steps.append("\u53d6\u4ee4\u724c\uff1aPOST /portal/api/tournaments/%s/token \u2192 \u5199 %s" % (a.tid, os.path.relpath(tokfile, ROOT)))
    steps.append("\u5230\u4f4d\uff1apython -X utf8 var/_ready_1024.py --tid %s --token-file %s" % (a.tid, a.token_file))

    # \u2462 \u65f6\u95f4\u8868
    start = None
    if t0.get("start_at"):
        start = dt.datetime.fromtimestamp(int(t0["start_at"]))
    if a.switch_at:
        sw = dt.datetime.strptime(a.switch_at, "%Y-%m-%d %H:%M:%S")
    elif start:
        sw = start - dt.timedelta(minutes=40)
    else:
        print("\u274c \u65e2\u65e0 --switch-at\uff0c\u4e5f\u8bfb\u4e0d\u5230\u5f00\u8d5b\u65f6\u95f4"); return 2
    sched = [("Switch", sw), ("SwitchRetry", sw + dt.timedelta(minutes=20)),
             ("SwitchLast", sw + dt.timedelta(minutes=30))]
    if start:
        sched.append(("TminusReady", start - dt.timedelta(minutes=5)))
        for i in range(4):
            sched.append(("After%d" % (i + 1), start + dt.timedelta(hours=3 + 1.5 * i)))
    print("=== \u8d5b\u4e8b\u5165\u573a\uff08%s\uff09===" % ("\u771f\u6267\u884c" if a.go else "dry-run"))
    print("  tid=%s  \u7b56\u7565=%s  \u4ee4\u724c\u6587\u4ef6=%s" % (a.tid, a.strategy, a.token_file))
    if t0:
        print("  \u95e8\u6237\uff1a%s | status=%s | \u5f00\u8d5b=%s | \u5df2\u62a5\u540d=%s | my_registered=%s"
              % (t0.get("name"), t0.get("status"),
                 dt.datetime.fromtimestamp(int(t0["start_at"])).strftime("%m-%d %H:%M") if t0.get("start_at") else "-",
                 t0.get("registered"), t0.get("my_registered")))
    if res:
        print("  \u5feb\u7167\u6062\u590d\u4fe1\u606f\uff1a%s \u00b7 bundles=%s \u00b7 started=%s" % (res["arms"], res["bundles"], res["started"]))
    for s in steps:
        print("  \u2461 " + s)
    for n, t in sched:
        print("  \u23f0 %-14s %s  (%s%s)" % (n, f(t), a.prefix, n))
    if not a.go:
        print("\uff08dry-run\uff1a\u672a\u6267\u884c\uff1b\u52a0 --go \u624d\u771f\u6ce8\u518c\u4efb\u52a1\u5e76\u62a5\u540d/\u5230\u4f4d\uff09")
        return 0

    # ---- \u771f\u6267\u884c ----
    if res:
        with io.open(RESUME, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(res, ensure_ascii=False))
        print("\u5df2\u5199\u5feb\u7167\u6062\u590d\u4fe1\u606f\uff1a%s" % RESUME)
    if t0 and not t0.get("my_registered"):
        try:
            st, body = post("/portal/api/tournaments/%s/register" % a.tid, cookie=ck)
            print("\u62a5\u540d HTTP %s %s" % (st, body[:120]))
        except Exception as e:
            print("\u26a0 \u62a5\u540d\u5931\u8d25\uff1a%s" % str(e)[:120])
    if not os.path.exists(tokfile):
        try:
            st, body = post("/portal/api/tournaments/%s/token" % a.tid, cookie=ck)
            d = json.loads(body); tk = d.get("token") or d.get("access_token")
            if tk:
                with io.open(tokfile, "w", encoding="utf-8") as fh:
                    fh.write(str(tk).strip() + "\n")
                print("\u5df2\u5199\u4ee4\u724c\u6587\u4ef6 %s" % tokfile)
        except Exception as e:
            print("\u26a0 \u53d6\u4ee4\u724c\u5931\u8d25\uff1a%s" % str(e)[:120])
    p = subprocess.run([sys.executable, "-X", "utf8", "var/_ready_1024.py", "--tid", a.tid,
                        "--token-file", a.token_file], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    print("\u5230\u4f4d\uff1arc=%s %s" % (p.returncode, (p.stdout or "").strip().splitlines()[-1:] or ""))
    reg = [["pwsh", "-NoProfile", "-File", "var/_register_4test_switch.ps1", "-At", f(t), "-TaskName", a.prefix + n,
            "-Strategy", a.strategy, "-TokenFile", a.token_file, "-TournamentId", a.tid, "-Go"] for n, t in sched[:3]]
    if start:
        reg.append(["pwsh", "-NoProfile", "-File", "var/_register_tminus_ready.ps1", "-At", f(start - dt.timedelta(minutes=5)),
                    "-TaskName", a.prefix + "TminusReady", "-Tid", a.tid, "-TokenFile", a.token_file, "-Go"])
        for i in range(4):
            reg.append(["pwsh", "-NoProfile", "-File", "var/_register_after_4test.ps1",
                        "-At", f(start + dt.timedelta(hours=3 + 1.5 * i)),
                        "-TaskName", a.prefix + "After%d" % (i + 1), "-Go"])
    for c in reg:
        p = subprocess.run(c, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        print("  \u6ce8\u518c %-22s rc=%s" % (c[c.index("-TaskName") + 1], p.returncode))
    print("\u2605 \u5165\u573a\u6ce8\u518c\u5b8c\u6210\uff1a\u8bf7\u7528 schtasks /query /tn %sSwitch /v /fo LIST \u6838\u5bf9\u52a8\u4f5c\u4e32" % a.prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
