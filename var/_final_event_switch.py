# -*- coding: utf-8 -*-
"""`var/_final_event_switch.py` —— **10/10 \u6b63\u5f0f\u8d5b\u7684\u81ea\u52a8\u4e0a\u7ebf**\uff08\u628a\u6700\u540e\u4e00\u6b65\u4eba\u5de5\u964d\u5230\u201c\u53ea\u9700\u653e\u4e00\u4e2a\u4ee4\u724c\u6587\u4ef6\u201d\uff09\u3002

## \u4f9d\u636e

\u8fd0\u884c\u624b\u518c \u00a78\uff1a\u6b63\u5f0f\u8d5b\u4e0a\u7ebf = `\u6362\u65b0\u4ee4\u724c + \u65b0\u8d5b\u4e8b id` \u2192 `_ready_1024`\uff08T-30/T-5\uff09\u2192 `_switch_to_official.ps1 -Strategy <\u6700\u7ec8\u81c2> ...`\u3002
\u4e2d\u95f4\u90a3\u4e24\u6b65\u90fd\u662f\u73b0\u6210\u811a\u672c\uff0c**\u53ea\u5dee\u201c\u4ee4\u724c\u6587\u4ef6\u201d\u8fd9\u4e00\u4e2a\u4eba\u5de5\u8f93\u5165**\u3002\u672c\u811a\u672c\u628a\u5b83\u56fa\u5b9a\u6210\uff1a

1. \u8bfb `var/.final_arm.txt`\uff08**10/7 \u6362\u4e0a\u7684\u90a3\u4e2a\u81c2**\uff09\uff1b
2. \u8bfb\u4ee4\u724c\u6587\u4ef6\uff08\u9ed8\u8ba4 `var/.token_final_20261010`\uff0c\u53ef\u7528 `--token-file` \u6539\uff09\uff1b
3. \u89e3\u6790\u8d5b\u4e8b id\uff1a\u4f18\u5148 `--tid`\uff0c\u5426\u5219\u7528\u95e8\u6237\u201c\u552f\u4e00 registering \u8d5b\u4e8b\u201d\uff08\u4e0e `_ready_1024.py` \u540c\u4e00\u53e3\u5f84\uff09\uff1b
4. \u8c03\u7528**\u73b0\u6210** `var/_switch_to_official.ps1 -Strategy <arm> -TokenFile <tok> -TournamentId <tid>`\uff08**\u4e0d\u4f20 `-AllowNotReady`**\uff09\u21d2 \u5b83\u81ea\u5e26 preflight / rules_guard / \u54e8\u5175 / spec / POST ready / \u7b49\u7a7a\u6863 / \u8d77 keepalive\uff1b
5. \u4e8b\u540e\u6821\u9a8c\uff1a`.official_mode` \u5728\u4f4d + `_official_keepalive.py` \u5728\u8dd1\uff0c\u5426\u5219\u8bb0\u4e0b\u5f02\u5e38\u884c\u4f9b\u4eba\u5de5\u3002

**\u4efb\u4f55\u4e00\u4e2a\u524d\u63d0\u4e0d\u6ee1\u8db3\uff08\u7f3a\u6700\u7ec8\u81c2 / \u7f3a\u4ee4\u724c / \u89e3\u4e0d\u5230 tid\uff09\u21d2 \u76f4\u63a5\u9000\u51fa\u5e76\u8bb0\u65e5\u5fd7\uff0c\u7edd\u4e0d\u731c\u53c2\u6570**\u3002

\u7ea2\u7ebf\uff1a\u4e0d\u5f3a\u6740\u4efb\u4f55\u5bf9\u5c40\uff08\u7b49\u7a7a\u6863\u4ea4\u7ed9 `_switch_to_official.ps1`\uff09\uff1b\u4e0d\u6539 `bot/`\uff1b\u4e0d\u624b\u6413\u72b6\u6001\u6587\u4ef6\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_final_event_switch.py --dry-run
    python -X utf8 var/_final_event_switch.py --go
"""
from __future__ import annotations
import argparse
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
LOG = os.path.join(ROOT, "var", "_final_event_switch.log")
FINAL_ARM = os.path.join(ROOT, "var", ".final_arm.txt")
TOKEN_DEFAULT = os.path.join(ROOT, "var", ".token_final_20261010")
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def resolve_tid(server="https://10.240.169.190:18080"):
    """\u95e8\u6237\u552f\u4e00 registering \u8d5b\u4e8b\u7684 tid\uff08\u4e0e `_ready_1024.py` \u540c\u53e3\u5f84\uff09\u3002"""
    import ssl
    import urllib.request
    ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
    req = urllib.request.Request(server + "/portal/api/tournaments", headers={"Cookie": ck})
    with urllib.request.urlopen(req, timeout=20, context=ssl._create_unverified_context()) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    ts = d if isinstance(d, list) else (d.get("tournaments") or [])
    reg = [t for t in ts if str(t.get("status")) == "registering" and t.get("id")]
    if len(reg) == 1:
        return str(reg[0]["id"]), str(reg[0].get("name") or "")
    return "", ("\u5171 %d \u4e2a registering \u8d5b\u4e8b" % len(reg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--token-file", default=TOKEN_DEFAULT)
    ap.add_argument("--final-file", default=FINAL_ARM)
    ap.add_argument("--tid", default="")
    a = ap.parse_args()

    if not os.path.exists(a.final_file):
        log("!! \u7f3a %s\uff08\u6700\u7ec8\u81c2\u672a\u5b9a\uff09\u21d2 \u4e0d\u4e0a\u7ebf" % os.path.basename(a.final_file))
        return 2
    arm = io.open(a.final_file, encoding="utf-8-sig").read().strip()
    if not arm:
        log("!! .final_arm.txt \u4e3a\u7a7a \u21d2 \u4e0d\u4e0a\u7ebf")
        return 2
    if not os.path.exists(a.token_file):
        log("!! \u7f3a\u4ee4\u724c\u6587\u4ef6 %s\uff08\u9700\u5148\u628a\u5f53\u5929\u4ee4\u724c\u5b58\u5230\u8fd9\u91cc\uff09\u21d2 \u4e0d\u4e0a\u7ebf" % a.token_file)
        return 2
    tid = a.tid
    if not tid:
        try:
            tid, name = resolve_tid()
        except Exception as e:
            log("!! \u95e8\u6237\u53d6 tid \u5931\u8d25\uff1a%s \u21d2 \u4e0d\u4e0a\u7ebf" % str(e)[:80])
            return 2
        if not tid:
            log("!! \u95e8\u6237\u89e3\u4e0d\u5230\u552f\u4e00 registering \u8d5b\u4e8b\uff08%s\uff09\u21d2 \u4e0d\u4e0a\u7ebf" % name)
            return 2
        log("\u95e8\u6237\u89e3\u6790\u5230\u8d5b\u4e8b\uff1a%s\uff08tid=%s\uff09" % (name, tid))
    import _ps
    cmd = _ps.argv("-NoProfile", "-File", "var/_switch_to_official.ps1",
                   "-Strategy", arm, "-TokenFile", a.token_file, "-TournamentId", tid)
    log("\u5373\u5c06\u4e0a\u7ebf\uff1a" + " ".join(cmd))   # \u4e0d\u4f20 -AllowNotReady\uff08fail-safe\uff09
    if a.dry_run or not a.go:
        print("\uff08dry-run\uff1a\u672a\u6267\u884c\uff1b\u52a0 --go \u624d\u771f\u8dd1\uff09")
        return 0
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=3600)
    tail = "\n".join((p.stdout or "").strip().splitlines()[-8:])
    log("switch rc=%s\n%s" % (p.returncode, tail))
    if p.returncode != 0:
        log("!! \u4e0a\u7ebf\u811a\u672c\u975e 0 \u21d2 \u8bf7\u770b\u4e0a\u9762\u8f93\u51fa\uff08\u672a\u5f3a\u6740\u4efb\u4f55\u5bf9\u5c40\uff09")
        return p.returncode
    ok_flag = os.path.exists(OFFICIAL)
    import psutil
    ka = [pr.info["pid"] for pr in psutil.process_iter(["pid", "cmdline"])
          if "_official_keepalive.py" in " ".join(str(x) for x in (pr.info.get("cmdline") or []))]
    log("\u2605 \u4e0a\u7ebf\u6821\u9a8c\uff1a.official_mode=%s\uff0ckeepalive=%s" % (ok_flag, ka))
    return 0 if (ok_flag and ka) else 2


if __name__ == "__main__":
    sys.exit(main())