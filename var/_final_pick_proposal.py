# -*- coding: utf-8 -*-
"""`var/_final_pick_proposal.py` —— **10/5 选臂预提案**\uff1a\u63d0\u524d\u628a\u201c\u6700\u7ec8\u81c2\u5019\u9009 + \u4f9d\u636e\u201d\u7b97\u51fa\u6765\u3002

\u4e3a\u4ec0\u4e48\uff1a10/7 09:00 \u7684\u6362\u81c2\u4f9d\u8d56 `var/.final_arm.txt`\uff08\u7f3a\u5931\u5219\u62d2\u7edd\uff0c\u5b81\u53ef\u4e0d\u6362\u4e5f\u4e0d\u731c\uff09\u3002
\u800c 10/5\u201310/6 \u7684\u9009\u81c2\u4f9d\u636e\u662f\u73b0\u6210\u5de5\u5177 `var/_pick_arm.py`\uff08\u5f3a\u624b\u623f\u5206/\u623f \u2192 \u4e24\u534a Pareto \u2192 \u7b2c1\u7387 \u2192 \u2026\uff09\u3002
\u672c\u811a\u672c\u628a\u5b83\u7684\u8f93\u51fa\u843d\u76d8\u6210\u4e00\u4efd**\u53ef\u76f4\u63a5\u7167\u7740\u5199 `.final_arm.txt` \u7684\u63d0\u6848**\uff0c\u907f\u514d\u4e34\u573a\u624b\u5fd9\u3002

\u53ea\u8bfb\uff1a\u53ea\u8dd1 `_pick_arm.py`\uff08\u8bfb\u53f0\u8d26 + \u699c\u5355\uff09\u5e76\u5199\u81ea\u5df1\u7684\u63d0\u6848\u6587\u4ef6\uff1b\u4e0d\u6539 `.ab_mode`\u3001\u4e0d\u6539 `_keeper_strategy.txt`\u3001\u4e0d\u52a8\u4efb\u4f55\u8fdb\u7a0b\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_final_pick_proposal.py            # \u6309\u5f53\u524d .ab_mode \u51fa\u63d0\u6848
    python -X utf8 var/_final_pick_proposal.py --dry-run  # \u53ea\u6253\u5370
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
AB = os.path.join(ROOT, "var", ".ab_mode")
OUT = os.path.join(ROOT, "var", "_final_pick_proposal.txt")
LOG = os.path.join(ROOT, "var", "_final_pick_proposal.log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rooms", type=int, default=30)
    ap.add_argument("--strong-top", type=int, default=32)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(AB):
        print("\u65e0 `.ab_mode`\uff08\u6ca1\u6709\u5728\u8dd1\u7684\u6bb5\uff09\u21d2 \u4e0d\u51fa\u63d0\u6848")
        return 0
    cfg = json.loads(io.open(AB, encoding="utf-8-sig").read())
    if isinstance(cfg.get("arms"), list):
        arms = [str(x) for x in cfg["arms"]]
    else:
        arms = [x for x in (cfg.get("a"), cfg.get("b")) if x]
    started = str(cfg.get("started") or "")
    baseline = str((cfg.get("bundles") or arms[:1])[0])
    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_pick_arm.py"),
           "--since", started, "--min-rooms", str(a.min_rooms), "--strong-top", str(a.strong_top)]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    body = (p.stdout or "").strip()
    head = (
        "===== \u6700\u7ec8\u81c2\u9009\u62e9\u63d0\u6848 %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S")
        + "\u5f53\u524d\u6218\u5f79\u7a97\u53e3 started=%s\n\u53c2\u4e0e\u81c2\uff1a%s\n\u7b7e\u540d\u57fa\u7ebf\uff08bundles\uff09\uff1a%s\n" % (started, ", ".join(arms), baseline)
        + "\uff08\u4f9d\u636e\uff1avar/_pick_arm.py \u7684 \u00a7V.66 \u5e8f\u5217\uff1a\u5f3a\u624b\u623f\u5206/\u623f \u2192 \u4e24\u534a Pareto \u2192 \u7b2c1\u7387 \u2192 \u6700\u8fd1\u5224\u8bcd \u2192 \u4fdd\u6301\u73b0\u72b6\uff09\n"
        + "\u2605 \u53ea\u5141\u8bb8\u201c\u5df2\u5224\u6b63\u7684\u5c42\u201d\u8fdb\u6700\u7ec8\u81c2\uff08\u00a7V.161/\u00a7V.165\uff09\uff1b\u4e0d\u90e8\u7f72\u4ece\u672a\u5224\u6b63\u8fc7\u7684\u81c2\u3002\n"
        + "\u2605 \u5199\u5165\u65b9\u5f0f\uff08\u786e\u8ba4\u540e\uff09\uff1aecho <arm> > var/.final_arm.txt\n"
        + "-" * 78 + "\n"
    )
    # ★ R1445：追补"分层读数"——**只作读数，不改 §V.66 判据**。
    #   动机：top32 只出现在"房里有 top32"的房里 ⇒ 单独看 top32 行本就是强手房口径；
    #   而"强手房 ≥1"与"强手房 ≥2（决赛相似层）"的优劣**可能方向相反**（役 2 本机实测：
    #   ≥1 层 speedc151 更好、≥2 层 speedvalue 更好）。正式赛（16 人强场）更接近 ≥2 层 ⇒ 两层都要看。
    strat = ""
    try:
        q = subprocess.run([sys.executable, "-X", "utf8",
                            os.path.join(ROOT, "var", "_verdict_by_elite.py"),
                            "--since", started, "--arms", ",".join(arms)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        strat = (q.stdout or "").strip()
    except Exception as e:
        strat = "（分层读数不可得：%s）" % str(e)[:60]
    text = head + body + "\n"
    if strat:
        text += ("\n" + "=" * 78 + "\n"
                 + "分层读数（R1445 追补：只作读数，**不改 §V.66 判据**）\n"
                 + "★ 为何要看：正式赛是强场（16 人）⇒ 至少并读「强手房 ≥1」与「强手房 ≥2」两层；\n"
                 + "  两层优劣**可能方向相反**（役 2 实测：≥1 层 c151 好、≥2 层 value 好）。\n"
                 + "=" * 78 + "\n" + strat + "\n")
    if a.dry_run:
        print(text)
        return 0
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s \u5df2\u51fa\u63d0\u6848\uff08\u7a97\u53e3 %s\uff0c\u81c2 %s\uff09\u21d2 %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), started, ",".join(arms), os.path.relpath(OUT, ROOT)))
    print(" proposal -> %s" % os.path.relpath(OUT, ROOT))
    print(body[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())