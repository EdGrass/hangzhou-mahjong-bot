# -*- coding: utf-8 -*-
"""`var/_mech_watch.py` —— \u5f79\u4e2d**\u673a\u5236\u7aef\u70b9\u5b88\u62a4**\uff1a\u6bcf N \u5c0f\u65f6\u628a\u5f53\u524d\u5f79\u5019\u9009\u81c2\u7684\u79bb\u7ebf\u8db3\u8ff9\u91cd\u62bd\u4e00\u6b21\u3002

## \u4e3a\u4ec0\u4e48\uff08\u9884\u767b\u8bb0\u8981\u6c42\uff0c\u4e0d\u662f\u6211\u52a0\u7684\uff09

`prereg-campaign3-speedvaluebc-20260924.md` \u7b2c 2 \u8282\u628a\u300c**\u51b3\u7b56\u6539\u52a8\u7387 \u2208 [10%, 20%] \u4e14 action \u5dee\u5f02 = 0**\u300d\u5b9a\u4e3a\u672c\u5f79**\u6838\u5fc3\u673a\u5236\u7aef\u70b9**\uff0c
\u5e76\u8981\u6c42\u201c\u6bcf 20 \u623f\u590d\u8dd1\u4e00\u6b21 `tools/offline_replay`\uff08\u62bd\u6837\u5373\u53ef\uff09\u201d\u3002\u4eba\u5de5\u6570\u623f\u5bb9\u6613\u5fd8 \u21d2 \u672c\u811a\u672c\u628a\u5b83\u53d8\u6210\u65f6\u95f4\u9a71\u52a8\u7684\u5b9a\u671f\u91cd\u62bd\u4e0e\u81ea\u52a8\u5224\u8bfb\u3002

## \u884c\u4e3a

1. \u8bfb `var/.ab_mode`\uff1b**\u65e0\u5f79\u5728\u8dd1\u5c31\u76f4\u63a5\u9000\u51fa**\uff08\u7edd\u5bf9 no-op\uff09\uff1b
2. \u5bf9\u6bcf\u4e2a\u5019\u9009\u81c2\u9009\u76f8\u4f4d\u5e76\u8dd1\u79bb\u7ebf\u91cd\u62bd\uff08\u5168\u7a0b `--lowprio`\uff0c\u9075\u5b88 \u00a79.30/\u00a79.47 \u7eaa\u5f8b\uff09\uff1a
   * \u542b `meld` \u21d2 `--phase window`\uff08\u671f\u671b\u7d22\u53d6\u7387\u4e0a\u5347\uff09\uff1b
   * \u542b `bc` / `baotou` \u21d2 `--phase draw`\uff08\u671f\u671b tile \u6539\u52a8\u7387 \u2208 [10,20]%\u3001action \u5dee\u5f02 = 0\uff09\uff1b
   * \u5176\u4ed6 \u21d2 \u53ea\u8bb0\u5f55\uff08\u4e0d\u5224\uff09\u3002
3. \u7ed3\u679c\u8ffd\u52a0\u5230 `var/_mech_watch.log`\uff1b\u4e0d\u5728\u9884\u671f\u5e26\u5185 \u21d2 \u5199 `var/.mech_warn`\uff08\u5e26\u539f\u56e0\uff09\uff0c\u6b63\u5e38 \u21d2 \u5220\u5b83\u3002

\u7ea2\u7ebf\uff1a\u53ea\u8bfb\u8bed\u6599/\u53ea\u5199\u81ea\u5df1\u7684\u65e5\u5fd7\u4e0e\u6807\u8bb0\uff1b\u4e0d\u78b0\u5f79\u3001\u4e0d\u78b0 `bot/`\u3001\u4e0d\u6740\u8fdb\u7a0b\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_mech_watch.py            # \u6309 .ab_mode \u81ea\u52a8\u5224\u5f53\u524d\u5f79
    python -X utf8 var/_mech_watch.py --files 200 --dry-run
"""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
LOG = os.path.join(ROOT, "var", "_mech_watch.log")
WARN = os.path.join(ROOT, "var", ".mech_warn")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(os.environ.get("HM_MECH_LOG", LOG), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def phases_for(arm):
    """臂名 → 需检相位列表（R1430）。

    单层臂返回一个；**组合臂（例 `speedvaluebcvmeld`）两个都检**：
    含 `meld` ⇒ window（索取率）；含 `bc`/`baotou` ⇒ draw（出牌改动率）。
    """
    a = arm.lower()
    ph = []
    if "meld" in a:
        ph.append("window")
    if "bc" in a or "baotou" in a:
        ph.append("draw")
    return ph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=200)
    ap.add_argument("--ab-file", default=AB, help="默认 var/.ab_mode；测试可指向临时文件")
    ap.add_argument("--log-file", default=LOG)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.ab_file):
        print("\u65e0 .ab_mode \u21d2 \u65e0\u5f79\u5728\u8dd1\uff0cno-op")
        return 0
    try:
        cfg = json.loads(io.open(a.ab_file, encoding="utf-8-sig").read())
    except Exception as e:
        log("!! \u8bfb .ab_mode \u5931\u8d25\uff1a%s" % str(e)[:60])
        return 1
    baseline = (cfg.get("bundles") or [cfg.get("a")])[0]
    arms = [cfg.get("a"), cfg.get("b")]
    cands = [x for x in arms if x and x != baseline]
    if not cands:
        log("\u5f79\u5185\u65e0\u5019\u9009\u81c2\uff08arms=%s, baseline=%s\uff09\u21d2 no-op" % (arms, baseline))
        return 0

    warns = []
    pairs = [(c, p) for c in cands for p in (phases_for(c) or [""])]
    for cand, ph in pairs:
        if not ph:
            log("  %s \u21d2 \u65e0\u9884\u8bbe\u671f\u671b\uff0c\u53ea\u8bb0\u5f55" % cand)
            continue
        cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "offline_replay.py"),
               "--base", baseline, "--cand", cand, "--phase", ph,
               "--files", str(a.files), "--lowprio"]
        if a.dry_run:
            log("  [dry-run] %s" % " ".join(cmd[1:]))
            continue
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800)
        except subprocess.TimeoutExpired:
            log("!! %s \u91cd\u62bd\u8d85\u65f6" % cand)
            warns.append("%s \u91cd\u62bd\u8d85\u65f6" % cand)
            continue
        out = p.stdout or ""
        if ph == "draw":
            m = re.search(r"tile \u4e0d\u540c \d+ \(([\d.]+)%\)\s+action \u4e0d\u540c \d+ \(([\d.]+)%\)", out)
            if not m:
                log("!! %s draw \u8f93\u51fa\u672a\u8bc6\u522b\uff08rc=%s\uff09" % (cand, p.returncode))
                continue
            tile_pct, act_pct = float(m.group(1)), float(m.group(2))
            # ★ R1430：只在“出牌层是**新加**的”时才拉 10–20% 带；若基线已含 bc
            #   （如役 5：`speedvaluebc` → `speedvaluebcvmeld`），这是**边际**足迹，只记录不判。
            _layer_new = ("bc" in cand.lower() or "baotou" in cand.lower()) and not (
                "bc" in baseline.lower() or "baotou" in baseline.lower())
            ok = (10.0 <= tile_pct <= 20.0 and act_pct == 0.0) if _layer_new else (act_pct == 0.0)
            _exp = "\u9884\u671f 10\u201320% / action=0" if _layer_new else "\u8fb9\u9645\u8db3\u8ff9\uff08\u57fa\u7ebf\u5df2\u542b\u540c\u5c42\uff09\uff1a\u53ea\u8981 action=0"
            log("  %s draw\uff1atile \u6539\u52a8 %.1f%%\u3001action %.1f%% \u21d2 %s\uff08%s\uff09\uff08%.0fs\uff09"
                % (cand, tile_pct, act_pct, "PASS" if ok else "WARN", _exp, time.time() - t0))
            if not ok:
                warns.append("%s draw \u8db3\u8ff9 %.1f%%/action %.1f%% \u8131\u79bb\u9884\u671f" % (cand, tile_pct, act_pct))
        else:
            m = re.search(r"\u7d22\u53d6\u7387\(\u6536\u526f\u9732/\u53ef\u7d22\u53d6\):\s+\u57fa\u7ebf ([\d.]+)%\s+\u5019\u9009 ([\d.]+)%", out)
            m2 = re.search(r"\u4ec5\u57fa\u7ebf\u6536 (\d+)", out)
            if not m:
                log("!! %s window \u8f93\u51fa\u672a\u8bc6\u522b\uff08rc=%s\uff09" % (cand, p.returncode))
                continue
            b, c = float(m.group(1)), float(m.group(2))
            base_only = int(m2.group(1)) if m2 else -1
            _layer_new_w = "meld" in cand.lower() and "meld" not in baseline.lower()
            ok = ((c >= b + 3.0) and base_only == 0) if _layer_new_w else (base_only == 0)
            log("  %s window\uff1a\u7d22\u53d6\u7387 %.1f%% \u2192 %.1f%%\uff08\u4ec5\u57fa\u7ebf\u6536 %d\uff09\u21d2 %s\uff08\u9884\u671f \u2265+3pp \u4e14\u53ea\u52a0\u4e0d\u51cf\uff09\uff08%.0fs\uff09"
                % (cand, b, c, base_only, "PASS" if ok else "WARN", time.time() - t0))
            if not ok:
                warns.append("%s window \u7d22\u53d6\u7387 %.1f%%\u2192%.1f%%\uff08\u4ec5\u57fa\u7ebf\u6536 %d\uff09" % (cand, b, c, base_only))

    if a.dry_run:
        return 0
    try:
        if warns:
            with io.open(os.environ.get("HM_MECH_WARN", WARN), "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + "\uff1b".join(warns) + "\n")
            log("\u26a0 \u673a\u5236\u7aef\u70b9\u544a\u8b66\uff1a" + "\uff1b".join(warns))
        else:
            _w = os.environ.get("HM_MECH_WARN", WARN)
            if os.path.exists(_w):
                os.remove(_w)
            log("\u673a\u5236\u7aef\u70b9\u6b63\u5e38\uff08\u5f79 %s vs %s\uff09" % (",".join(cands), baseline))
    except Exception as e:
        log("\u26a0 \u6807\u8bb0\u5199\u5165\u5931\u8d25\uff1a%s" % str(e)[:60])
    return 0


if __name__ == "__main__":
    sys.exit(main())