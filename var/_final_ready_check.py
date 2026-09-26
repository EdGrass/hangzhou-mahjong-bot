# -*- coding: utf-8 -*-
"""`var/_final_ready_check.py` —— **10/7\u201310/8 \u6700\u7ec8\u5c31\u7eea\u6821\u9a8c**\uff08\u53ea\u8bfb + \u5199\u81ea\u5df1\u7684\u62a5\u544a\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u7528\u6237\u6307\u4ee4\u201c**\u5728\u4e03\u53f7\u6362\u4e0a\u4f60\u80fd\u6413\u51fa\u6765\u7684\u6700\u5c4c\u7684\u6a21\u578b\uff0c\u51c6\u5907\u6700\u540e\u7684\u6bd4\u8d5b**\u201d\u3002
\u6362\u4e0a\u53bb\u4e4b\u540e\u5fc5\u987b\u6709\u4e00\u4e2a\u4e0d\u4f9d\u8d56\u8bb0\u5fc6\u7684\u68c0\u67e5\uff1a\u771f\u6b63\u5728\u8dd1\u7684\u7b56\u7565\u662f\u4e0d\u662f\u90a3\u4e2a\u6700\u7ec8\u81c2\u3001\u5f79\u662f\u4e0d\u662f\u5df2\u6536\u53e3\u3001
\u63d0\u4ea4\u7269\u68c0\u67e5\u662f\u4e0d\u662f\u8fc7\u3002\u9010\u6761\u7ed3\u679c\u5199 `var/_final_ready_check.out`\uff0c\u5e76\u843d\u4e00\u4e2a\u558a\u5f97\u5f88\u54cd\u7684\u6807\u8bb0\u6587\u4ef6\u3002

\u68c0\u67e5\u9879\uff08\u4efb\u4e00 FAIL \u5c31\u5199 `.FINAL_NOT_READY`\uff09\uff1a
  1. `var/.final_arm.txt` \u5b58\u5728\u4e14\u975e\u7a7a\uff1b
  2. \u8be5\u81c2\u5df2\u6ce8\u518c **\u4e14\u53ef\u5b9e\u4f8b\u5316**\uff08\u8c03\u7528\u771f\u5b9e factory\uff09\uff1b
  3. `var/.final_installed` \u5b58\u5728\u4e14\u81c2\u540d\u4e0e\u4e0a\u4e00\u81f4\uff08\u5373 10/7 \u7684 `_switch_final.py --go` \u771f\u8dd1\u8fc7\uff09\uff1b
  4. `var/_keeper_strategy.txt` == \u6700\u7ec8\u81c2\uff08\u771f\u6b63\u5728\u8dd1\u7684\u5c31\u662f\u5b83\uff09\uff1b
  5. `var/.ab_mode` \u4e0d\u5b58\u5728\uff08\u5f79\u5df2\u6536\u53e3\uff0c\u4e0d\u4f1a\u518d\u88ab A/B \u6539\u6210\u522b\u7684\u81c2\uff09\uff1b
  6. git \u5de5\u4f5c\u533a\u5e72\u51c0\u4e14\u672c\u5730 == origin/main\uff08\u63d0\u4ea4\u7269\u5c31\u662f\u8dd1\u7740\u7684\u4efd\uff09\uff1b
  7. `var/_prepare_submission.ps1` \u68c0\u67e5\u6a21\u5f0f rc==0\uff08\u63d0\u4ea4\u7269\u683c\u5f0f\u5408\u89c4\uff09\u3002
  8. \u2605 R1563\uff1a**10/10 \u7684\u4ee4\u724c\u5df2\u5728\u4f4d**\uff08`var/.token_final_20261010` \u5b58\u5728\u4e14\u975e\u7a7a\uff09\u2014\u2014
     \u5b83\u662f**\u552f\u4e00\u7684\u4eba\u5de5\u8f93\u5165**\uff08\xa7V.181\uff09\uff1a\u7f3a\u5b83 \u21d2 10/10 18:50 \u7684 `_final_event_switch` **fail-closed \u62d2\u7edd\u4e0a\u7ebf**\u3002
     10/7 10:30 / 10/8 09:00 / **10/9 09:00\uff08T-1\uff09** \u5404\u6536\u4e00\u6b21 \u21d2 \u628a\u5b83\u53d8\u6210**\u63d0\u524d\u7684\u53ef\u884c\u52a8\u63d0\u9192**\u3002

\u7528\u6cd5\uff1a python -X utf8 var/_final_ready_check.py
"""
from __future__ import annotations
import io
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
OUT = os.path.join(ROOT, "var", "_final_ready_check.out")
OK_MARK = os.path.join(ROOT, "var", ".FINAL_READY")
BAD_MARK = os.path.join(ROOT, "var", ".FINAL_NOT_READY")
FINAL_ARM = os.path.join(ROOT, "var", ".final_arm.txt")
MARKER = os.path.join(ROOT, "var", ".final_installed")
KEEPER = os.path.join(ROOT, "var", "_keeper_strategy.txt")
GUARD_OFF = os.path.join(ROOT, "var", ".rate_guard_off")   # ★ R1444：最终臂固定开关
AB = os.path.join(ROOT, "var", ".ab_mode")


def read(p):
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read().strip()
    except Exception:
        return ""


def main():
    lines = []
    bad = []

    def chk(name, ok, detail=""):
        lines.append("%s %s%s" % ("PASS" if ok else "FAIL", name, (" \u2014 " + detail) if detail else ""))
        if not ok:
            bad.append(name)

    arm = read(FINAL_ARM)
    chk("1 \u6700\u7ec8\u81c2\u5df2\u9009\u5b9a", bool(arm), "\u81c2=%r" % arm)
    ok_arm = False
    if arm:
        try:
            sys.path.insert(0, ROOT)
            from run_bot import STRATEGY_FACTORIES as F
            if arm not in F:
                chk("2 \u5df2\u6ce8\u518c\u4e14\u53ef\u5b9e\u4f8b\u5316", False, "\u672a\u6ce8\u518c")
            else:
                F[arm]()
                ok_arm = True
                chk("2 \u5df2\u6ce8\u518c\u4e14\u53ef\u5b9e\u4f8b\u5316", True, "ok")
        except Exception as e:
            chk("2 \u5df2\u6ce8\u518c\u4e14\u53ef\u5b9e\u4f8b\u5316", False, "%s: %s" % (type(e).__name__, str(e)[:80]))
    else:
        chk("2 \u5df2\u6ce8\u518c\u4e14\u53ef\u5b9e\u4f8b\u5316", False, "\u65e0\u81c2\u540d")
    inst = read(MARKER)
    chk("3 \u5df2\u771f\u6362\u4e0a\uff08.final_installed\uff09", bool(inst) and (("arm=" + arm) in inst),
        inst or "\u7f3a .final_installed\uff08\u672a\u8dd1 _switch_final.py --go\uff09")
    cur = read(KEEPER)
    # ★ R1444：熔断器必须已关 —— 否则 A/B 收口后 rate_guard 会把策略**静默改回** FALLBACK(speedtugc)，
    #   第 4 项会在 10/7 10:30 之后某次运行里悄悄变红（而不是"装完就稳"）。
    guard_off = os.path.exists(GUARD_OFF)
    chk("4 keeper \u7b56\u7565==\u6700\u7ec8\u81c2 \u4e14 \u7194\u65ad\u5df2\u5173",
        bool(arm) and cur == arm and guard_off,
        "keeper=%r \u7194\u65ad\u5173=%s" % (cur, guard_off))
    chk("5 \u5f79\u5df2\u6536\u53e3\uff08\u65e0 .ab_mode\uff09", not os.path.exists(AB),
        "\u4ecd\u5728 A/B\uff08.ab_mode \u5b58\u5728\uff09" if os.path.exists(AB) else "")
    try:
        st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                            text=True, timeout=60).stdout.strip()
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
        org = subprocess.run(["git", "rev-parse", "origin/main"], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
        chk("6 git \u5e72\u51c0\u4e14\u672c\u5730==origin/main", (not st) and head == org and bool(head),
            "dirty=%r head=%s origin=%s" % (st[:80], head[:8], org[:8]))
    except Exception as e:
        chk("6 git \u5e72\u51c0\u4e14\u672c\u5730==origin/main", False, str(e)[:60])
    try:
        import _ps
        cmd = _ps.argv("-NoProfile", "-File", "var/_prepare_submission.ps1")
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        tail = [l for l in (p.stdout or "").splitlines() if "FAIL" in l or "\u7ed3\u679c" in l][-4:]
        chk("7 \u63d0\u4ea4\u7269\u68c0\u67e5 rc==0", p.returncode == 0, "rc=%s %s" % (p.returncode, " | ".join(tail)))
    except Exception as e:
        chk("7 \u63d0\u4ea4\u7269\u68c0\u67e5 rc==0", False, str(e)[:80])

    # \u2605 R1563\uff1a\u628a\u300c10/10 \u7684\u4ee4\u724c\u300d\uff08\u552f\u4e00\u4eba\u5de5\u8f93\u5165\uff09\u53d8\u6210\u4e00\u6761**\u63d0\u524d\u7684\u68c0\u67e5\u9879**\u3002
    #   \u52a1\u5b9e\uff1a\u82e5\u5e73\u53f0\u5c1a\u672a\u53d1\u724c\uff0c\u8fd9\u6761 FAIL \u662f**\u9884\u671f\u7684\u63d0\u9192**\uff08\u5fc3\u8df3 0g \u4f1a\u8f6c\u8ff0 `.FINAL_NOT_READY`\uff09\u800c\u975e\u6545\u969c\uff1b
    #   \u5b83\u4e0d\u88ab\u4efb\u4f55\u5176\u5b83\u811a\u672c\u8bfb\u53d6 \u21d2 \u52a0\u8fd9\u4e00\u9879**\u4e0d\u4f1a\u963b\u65ad 10/8 \u7684\u63d0\u4ea4**\u3002
    _tok10 = os.path.join(ROOT, "var", ".token_final_20261010")
    _tok_ok = os.path.exists(_tok10) and bool(read(_tok10))
    chk("8 10/10 \u4ee4\u724c\u5df2\u5728\u4f4d\uff08var/.token_final_20261010\uff09", _tok_ok,
        "\u5df2\u5728\u4f4d" if _tok_ok else "\u7f3a\u6587\u4ef6/\u4e3a\u7a7a \u2014\u2014 **\u4eba\u5de5\u8f93\u5165\uff08\u5176\u4e00\uff09**\uff1a\u82e5\u5e73\u53f0\u5c1a\u672a\u53d1\u724c\u5c5e\u9884\u671f\uff1b"
                                  "\u2605 \u6700\u8fdf **10/10 18:00** \u524d\u653e\u597d\uff0c\u5426\u5219 18:50 \u4e0a\u7ebf\u4f1a fail-closed \u62d2\u7edd")

    # \u2605 R1565\uff1a\u7b2c\u4e5d\u9879 = **\u4eba\u5de5\u7533\u62a5\u9875\u63d0\u4ea4**\u7684\u6536\u636e\u3002
    #   \u4e3a\u4ec0\u4e48\u8981\u6709\uff1a\u673a\u5668\u80fd\u63a8\u4ed3\u5e93\uff08`_submit_final` 10/8 10:00\uff09\uff0c**\u4f46\u4e0d\u80fd\u66ff\u4eba\u4ea4\u8868**\uff1b\u800c\u4ea4\u8868\u6709\u786c\u622a\u6b62\uff0810/8 12:00\uff09\u3002
    #   \u5b83\u662f**\u81ea\u62a5\u6536\u636e**\uff08\u4e0e `.final_arm.txt` \u540c\u7c7b\uff1a\u4eba\u5199\u3001\u673a\u5668\u53ea\u8bfb\u5b58\u5728\u6027\uff09\u3002
    _form = os.path.join(ROOT, "var", ".SUBMITTED_FORM")
    _form_ok = os.path.exists(_form)
    chk("9 \u7533\u62a5\u9875\u5df2\u63d0\u4ea4\uff08\u4eba\u5de5\u6536\u636e var/.SUBMITTED_FORM\uff09", _form_ok,
        "\u5df2\u6709\u6536\u636e" if _form_ok else "\u7f3a\u6536\u636e \u2014\u2014 \u82e5\u4f60\u5df2\u63d0\u4ea4\u8fc7\u7533\u62a5\u9875\uff08\u4ed3\u5e93 URL \u56fa\u5b9a\u3001\u5148\u4ea4\u540e\u66f4\u4ee3\u7801\uff09\u21d2 \u5efa\u4e00\u884c\u5373\u53ef\uff1b"
                                  "\u5426\u5219 \u2605 **10/8 12:00 \u524d**\u628a `docs/\u7533\u62a5\u6b63\u6587-\u6700\u7ec8.md` \u6b63\u6587 + \u4ed3\u5e93\u94fe\u63a5\u63d0\u4ea4\u5230\u7533\u62a5\u9875\uff08\u673a\u5668\u53ea\u80fd\u63a8\u4ed3\uff09")

    hdr = "===== \u6700\u7ec8\u5c31\u7eea\u6821\u9a8c %s on %s =====" % (time.strftime("%Y-%m-%d %H:%M:%S"), socket.gethostname())
    out = "\n".join([hdr] + lines + ["\u7ed3\u679c\uff1a" + ("\u5168\u90e8 PASS" if not bad else "FAIL %d \u9879\uff1a%s" % (len(bad), "\u3001".join(bad))), ""])
    try:
        with io.open(OUT, "a", encoding="utf-8") as f:
            f.write(out)
    except Exception:
        pass
    print(out)
    try:
        for p in (OK_MARK, BAD_MARK):
            if os.path.exists(p):
                os.remove(p)
        with io.open(BAD_MARK if bad else OK_MARK, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + (" \u5f85\u4fee\uff1a" + "\u3001".join(bad) if bad else " ok\n"))
    except Exception:
        pass
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())