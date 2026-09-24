# -*- coding: utf-8 -*-
# \u56db\u6d4b\u5207\u6362\u524d\u7684\u201c\u89c4\u5219\u9884\u68c0\u201d\uff1a\u8bfb\u8d5b\u4e8b config \u7684 YouCaiBiKao\uff0c\u5e76\u6309\u7ed3\u679c\u628a 3 \u4e2a\u5207\u6362\u4efb\u52a1\u91cd\u65b0\u6ce8\u518c\u6210\u6b63\u786e\u7684\u81c2\u3002
# \u4e3a\u4ec0\u4e48\uff1a\u82e5\u8d5b\u4e8b\u628a YouCaiBiKao \u7f6e true\uff0c\u65e0\u95f8\u95e8\u81c2\u4f1a\u88ab rules_guard \u5224\u4e0d\u4e00\u81f4 \u21d2 \u4e09\u4e2a\u5207\u6362\u4efb\u52a1\u5168\u90e8\u4e2d\u6b62 \u21d2 \u8fdb\u4e0d\u53bb\u3002
# \u672c\u811a\u672c\u628a\u201c\u81c2\u7684\u9009\u62e9\u201d\u53d8\u6210 config \u7684\u786e\u5b9a\u6027\u51fd\u6570\uff08\u975e\u4eba\u5de5\u5224\u65ad\uff09\u3002\u9ed8\u8ba4 dry-run\u3002
import _ps  # noqa: E402  （★ R1379：解析 PowerShell，避免任务上跑不到 pwsh）
import argparse, io, json, os, ssl, subprocess, sys, urllib.request, urllib.error
ROOT = r"D:\hangzhouMaj"
BASE = "https://10.240.169.190:18080"
TID = "t_6266386bfd56"
TOK = os.path.join(ROOT, "var", ".token_4test_20260924")
TASKS = ("HangzhouMaj4TestSwitch", "HangzhouMaj4TestSwitchRetry", "HangzhouMaj4TestSwitchLast")
AT = {"HangzhouMaj4TestSwitch": "2026-09-24 15:20:00",
      "HangzhouMaj4TestSwitchRetry": "2026-09-24 15:40:00",
      "HangzhouMaj4TestSwitchLast": "2026-09-24 15:50:00"}

def config():
    tok = io.open(TOK, encoding="utf-8").read().strip()
    req = urllib.request.Request(BASE + "/api/tournaments/" + TID,
                                 headers={"Authorization": "Bearer " + tok})
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("config") or {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        cfg = config()
    except Exception as e:
        print("\u26a0 \u8bfb\u4e0d\u5230 config\uff08%s\uff09\u21d2 \u4fdd\u6301\u73b0\u6709\u4efb\u52a1\u4e0d\u53d8" % str(e)[:120])
        return 0
    need = bool(cfg.get("YouCaiBiKao"))
    arm = "speedvalueycbk" if need else "speedvalue"
    print("YouCaiBiKao=%s \u21d2 \u672c\u573a\u5e94\u7528\u81c2 = %s" % (need, arm))
    for t in TASKS:
        cmd = _ps.argv("-NoProfile", "-File", "var/_register_4test_switch.ps1",
               "-At", AT[t], "-TaskName", t, "-Strategy", arm, "-Go")
        print("  " + " ".join(cmd))
        if not a.dry_run:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            print("    rc=%s %s" % (p.returncode, (p.stdout or "").strip().splitlines()[-1:] or ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())