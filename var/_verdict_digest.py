# -*- coding: utf-8 -*-
"""`var/_verdict_digest.py` —— **判词当天的一屏摘要**（只读；把读卡要求的多条命令跑成一条）。

## 为什么

判词当天（例：9/28 役3）要按读卡跑很多条：每个候选一次 `_gate2`（主/副/护栏/机制）+
一次 `_strong_veto`（强手房两层），再加两半 Pareto 的两条。**漏跑一条就可能读错四格**。
本工具按**固定顺序**把它们跑完，把关键行摘出来写成一份报告，并在屏幕上打一屏摘要。

## 纪律

- **只读 + 下降优先级**：不改台账、不改 `bot/`、不动任何进程；重活（两半 Pareto）走 `_lowprio_run.py`。
- **不做判断**：只给读数与 rc；“采用/不采用”一律按该役读卡与预登记（本工具不会说“采用”两个字）。
- 输出：`var/_verdict_digest_<since去符号>.txt`（只写自己的报告）。

用法：
    python -X utf8 var/_verdict_digest.py --since "2026-09-25 20:52:39" --baseline speedvalue \
        --candidates speedvaluebc,speedvaluebaotouv5 --mechanism none
    python -X utf8 var/_verdict_digest.py ... --dry-run     # 只打印将跑的命令
"""
from __future__ import annotations
import argparse
import io
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "var")
KEY_PREFIXES = ("\u2605 \u5224\u5b9a\uff1a", "\u2605 \u5f3a\u624b\u623f\u5426\u51b3", "\u21d2 UNKNOWN",
                "\u5f3a\u624b\u623f(>=", "\u21d2 \u6837\u672c\u4e0d\u8db3", "\u7b2c1\u7387", "\u51c0\u5206/\u623f",
                "\u548c\u724c\u7387/\u623f(\u4e3b)", "\u526f\u9732/\u623f(\u673a\u5236)", "!!",
                "\u524d\u4e24\u540d\uff1a", "\u4e0d\u53ef\u533a\u5206", "\u5b9a\u6848\uff1a", "\u5426\u51b3\u9884\u68c0")


MARKERS = (".mech_warn", ".v_mech_unknown", ".ADOPT_V_MECH_STALL")


def mech_section(var_dir=None, n_log=5):
    """★ R1548：把**机制端点**的证据一并汇总（读卡 §0b/§0c 要求看的那些）。

    为什么：役3 的 V 机制**不在** `_gate2` 里（`--mechanism none`），而在 `_mech_watch` 写的
    `.mech_warn` / `.v_mech_unknown` / `_v_mech_readings.jsonl` / `_mech_watch.log`；摘要不汇总它们，
    读卡要求的那一半证据就漏了。返回 [(title, body)]（纯函数，可单测）。
    """
    import json as _json
    vd = var_dir or OUT_DIR
    out = []
    for name in MARKERS:
        fp = os.path.join(vd, name)
        if not os.path.exists(fp):
            out.append((name, "（不存在）"))
            continue
        try:
            with io.open(fp, encoding="utf-8-sig", errors="replace") as f:
                out.append((name, f.read().strip() or "(空)"))
        except Exception as e:
            out.append((name, "（读不出：%s）" % str(e)[:60]))
    # 最新一条**非 None** 的 V 机制读数（每臂）
    rp = os.path.join(vd, "_v_mech_readings.jsonl")
    last, any_rec = {}, False
    if os.path.exists(rp):
        try:
            with io.open(rp, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        d = _json.loads(ln)
                    except Exception:
                        continue
                    arm = str(d.get("arm") or "")
                    if not arm:
                        continue
                    any_rec = True
                    if d.get("ok") is not None or arm not in last:
                        last[arm] = d
        except Exception:
            pass
    if any_rec:
        for arm in sorted(last):
            d = last[arm]
            out.append(("V读数/%s" % arm, "ok=%s  %s" % (d.get("ok"), (d.get("why") or "")[:160])))
    else:
        out.append(("V读数", "（无 `_v_mech_readings.jsonl`）"))
    lp = os.path.join(vd, "_mech_watch.log")
    if os.path.exists(lp):
        try:
            with io.open(lp, encoding="utf-8", errors="replace") as f:
                tail = [x.rstrip() for x in f.read().splitlines() if x.strip()][-n_log:]
            out.append(("_mech_watch.log 末%d行" % n_log, "\n".join(tail) or "(空)"))
        except Exception:
            pass
    return out


def pick_lines(text, limit=14, extra=()):
    """从一份工具输出里挑出“关键行”（纯函数，可单测）。

    `extra` 是**额外要匹配的子串**（例：臂名）—— 两半 Pareto 的表行首列就是臂名，
    不给 extra 的话那两段会是空的（实测过）。
    """
    pats = tuple(KEY_PREFIXES) + tuple(x for x in (extra or ()) if x)
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if any(s.startswith(pp.strip()) or (pp.strip() and pp.strip() in s) for pp in pats):
            out.append(s)
    return out[-limit:]


def cmds_for(since, baseline, cands, mechanism, min_rooms, strong_top):
    """★ 固定顺序：每个候选 gate2 + veto，最后两半 Pareto。返回 [(step, [cmd...])]。"""
    py = sys.executable
    low = os.path.join(ROOT, "var", "_lowprio_run.py")
    steps = []
    for c in cands:
        steps.append(("gate2/%s" % c,
                      [py, "-X", "utf8", os.path.join(ROOT, "var", "_gate2.py"),
                       "--since", since, "--baseline", baseline, "--candidate", c,
                       "--mechanism", mechanism, "--min-rooms", str(min_rooms)]))
    for c in cands:
        steps.append(("veto/%s" % c,
                      [py, "-X", "utf8", os.path.join(ROOT, "var", "_strong_veto.py"),
                       "--since", since, "--baseline", baseline, "--candidate", c]))
    # \u2605 R1553\uff1a**\u5f795 \u7684\u4e3b\u7aef\u70b9\u662f `_pick_arm` \u7684\u5f3a\u624b\u5206/\u623f**\uff08\u8bfb\u5361 \u00a71\uff09\uff0c\u4e0d\u653e\u8fdb\u6765\u5c31\u4f1a\u6f0f\u4e3b\u7aef\u70b9\u3002
    steps.append(("pick_arm(\u5f3a\u624b\u623f\u5206/\u623f\uff1b\u5f795 \u4e3b\u7aef\u70b9)",
                  [py, "-X", "utf8", os.path.join(ROOT, "var", "_pick_arm.py"),
                   "--since", since, "--min-rooms", str(min_rooms), "--strong-top", str(strong_top)]))
    steps.append(("half-A(\u80e1\u724c\u7387\u7f3a\u53e3\u4e24\u6bb5\u5206\u89e3)",
                  [py, "-X", "utf8", low, "--", py, "-X", "utf8",
                   os.path.join(ROOT, "tools", "hu_gap_split.py"),
                   "--dir", "recent", "--since", since, "--by-arm"]))
    steps.append(("half-B(\u540c\u5e2d\u5934\u5bf9\u5934 TOP%d)" % strong_top,
                  [py, "-X", "utf8", low, "--", py, "-X", "utf8",
                   os.path.join(ROOT, "var", "_seat_h2h.py"),
                   "--since", since, "--by-arm", "--top", str(strong_top)]))
    return steps


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidates", required=True, help="\u9017\u53f7\u5206\u9694")
    ap.add_argument("--mechanism", default="none", choices=("none", "melds", "gangs", "pairs"))
    ap.add_argument("--min-rooms", type=int, default=80)
    ap.add_argument("--strong-top", type=int, default=32)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cands = [x.strip() for x in a.candidates.split(",") if x.strip()]
    if not cands:
        ap.error("\u9700\u8981 --candidates")
    steps = cmds_for(a.since, a.baseline, cands, a.mechanism, a.min_rooms, a.strong_top)
    if a.dry_run:
        for name, cmd in steps:
            print("%-34s %s" % (name, " ".join(cmd[1:])))
        print("(\u8bd5\u8dd1\uff1a\u672a\u6267\u884c\u3001\u672a\u5199\u62a5\u544a)")
        return 0
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^0-9]", "", a.since) or stamp
    # ★ R1550：文件名带**时间戳** —— 同一窗口可能跑多次（例：9/27 部分数据、9/28 判词），
    #   不能把上一次的证据覆盖掉（本项目的证据链习惯：只追加、不覆写）。
    path = os.path.join(OUT_DIR, "_verdict_digest_%s_%s.txt" % (safe, stamp))
    digest, codes = [], {}
    _arms = [a.baseline] + cands
    with io.open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\u5224\u8bcd\u5f53\u5929\u6458\u8981  %s\nsince=%s baseline=%s candidates=%s mechanism=%s min_rooms=%d\n"
                  % (time.strftime("%Y-%m-%d %H:%M:%S"), a.since, a.baseline,
                     ",".join(cands), a.mechanism, a.min_rooms))
        # ★ R1548：机制端点（读卡 §0b/§0c）—— `_gate2 --mechanism none` 看不到这一半证据
        out.write("\n---- 机制端点（读卡 §0b/§0c 要求看的）----\n")
        for _t, _b in mech_section():
            out.write("[%s] %s\n" % (_t, _b.replace("\n", "\n    ")))
        for name, cmd in steps:
            t0 = time.time()
            try:
                p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=3000)
                body, rc = (p.stdout or "") + (p.stderr or ""), p.returncode
            except Exception as e:
                body, rc = "(\u8dd1\u4e0d\u52a8\uff1a%s)" % str(e)[:120], 99
            codes[name] = rc
            out.write("\n" + "=" * 78 + "\n$ %s\n[rc=%s  %.0fs]\n"
                      % (" ".join(cmd[1:]), rc, time.time() - t0))
            out.write(body)
            # ★ 两半 Pareto 的表行首列是臂名 ⇒ 额外按臂名匹配（否则那两段为空）
            _byarm = name.startswith("half-") or name.startswith("pick_arm")
            digest.append((name, rc, pick_lines(body, extra=(_arms if _byarm else ()))))
    print("\n===== 机制端点（读卡 §0b/§0c；_gate2 --mechanism none 看不到这一半）=====")
    for _t, _b in mech_section():
        print("  [%s] %s" % (_t, _b.replace("\n", " | ")[:200]))
    print("\n===== \u5224\u8bcd\u5f53\u5929\u6458\u8981\uff08\u53ea\u8bfb\uff1b\u4e0d\u505a\u5224\u65ad\uff09=====")
    for name, rc, lines in digest:
        print("\n-- %s   rc=%s" % (name, rc))
        for ln in lines:
            print("   " + ln)
    # ★ R1550：跨盘符时 `os.path.relpath` 会抛 ValueError（Windows）——
    #   不能在“报告已经写完”之后才崩；退回绝对路径。
    try:
        _shown = os.path.relpath(path, ROOT)
    except Exception:
        _shown = path
    print("\n\u62a5\u544a：%s" % _shown)
    print("\u2605 \u8bfb\u6cd5\uff1a\u6309**\u672c\u5f79\u8bfb\u5361**\uff08\u5f793 \u2192 yaku3-verdict-readcard.md \u00a70/\u00a70b/\u00a70c\uff1b"
          "\u5f794/5 \u5404\u81ea\u8bfb\u5361\uff09\uff1b\u5f3a\u624b\u623f\u82e5\u67d0\u5c42\u4e0d\u8db3 15 \u623f/\u81c2 \u2192 \u6309\u9884\u767b\u8bb0\u53ea\u8bb0\u5f55\uff0c"
          "\u4f46**\u5fc5\u987b\u4eba\u8bfb\u8be5\u5c42\u539f\u503c\u65b9\u5411**\u3002")
    return 0


if __name__ == "__main__":
    sys.exit(main())
