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
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
OUT = os.path.join(ROOT, "var", "_final_pick_proposal.txt")
LOG = os.path.join(ROOT, "var", "_final_pick_proposal.log")
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
B2 = os.path.join(ROOT, "var", ".B2_CANDIDATES")


def read_text(path):
    """读一个小文本文件（不存在/读失败 ⇒ ""），句柄必关。"""
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            return f.read().strip()
    except Exception:
        return ""


def parse_b2(text):
    """★ R1535：解析 `var/.B2_CANDIDATES` ⇒ (窗口, [臂…])。

    文件样（`_adopt_pair` 写）：
        2026-09-26 05:50 役三层 B2 备选臂（窗口 since=2026-09-25 20:52:39；预登记：…）
          speedvaluebc —— 机制成立、主端点未证实（判词：…）
        注：他们**没有**通过预登记判词 ⇒ …
    """
    win, arms = "", []
    for ln in (text or "").splitlines():
        raw = (ln or "").rstrip()
        s = raw.strip()
        if not win:
            m = re.search(r"since=([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})", s)
            if m:
                win = m.group(1)
        # 只认“**保留缩进**的两空格 + ——”的臂行（标题/注/说明都不算）——
        # 判缩进必须看 raw，不能看 strip 后的 s（否则恒为假：测试当场抓到过）。
        if not raw.startswith("  ") or u"——" not in s:
            continue
        arm = s.split(u"——", 1)[0].strip()
        if arm and (" " not in arm) and arm not in arms:
            arms.append(arm)
    return win, arms


def b2_section(b2txt, min_rooms=30, strong_top=32):
    """★ R1535：B2 备选臂的**并行比较材料**（只追加读数，不改 §V.66 判据）。

    为什么要有：campaign3 §4 B2 / campaign7 §4 B2 都要求把「机制成立、主端点未证实」的臂
    **保留为正式赛备选**、与 §V.66 口径**并行比较**；而 `_adopt_pair` 把它们落进
    `.B2_CANDIDATES` 之后，**除了心跳 0d 念一遍，没有任何脚本生成"比较材料"** ⇒
    10/5 提案（唯一的人工决策材料）里看不到这些臂的读数 ⇒ 预登记要求的"并行比较"落空。
    **纪律（R1557 订正）**：B2 臂按 §V.161 规则 4 **不进自动池**；并且按 **§V.161 A.1**（与 campaign8 §4-4 同口径）——**没过阈值的臂不进最终臂候选池**
    ⇒ 本段**只作旁证**，**不得据此写 `.final_arm.txt`**。（§V.247 的“提案比较窗口内全部臂”是指**列出/比较**的范围，不是授权部署未判正臂。）
    """
    win, arms = parse_b2(b2txt)
    out = ("\n" + "=" * 78 + "\n"
           + "★ B2 备选臂（R1535）—— 预登记要求「保留为备赛备选、与 §V.66 口径并行比较」\n"
           + "★ 纪律：B2 = **机制成立、主端点未证实** ⇒ 按 §V.161 规则 4 **不进自动池**；\n"
           + "  ★ R1557 订正：**未判正的臂（含 B2）不入最终臂候选池**"
           + "（§V.161 A.1“没过阈值的不进候选池” + campaign8 §4-4）"
           + "  ⇒ 本段**只作旁证**，**不得据此写 `.final_arm.txt`**；人可在提案里**已判正的臂**之间换行。\n"
           + "=" * 78 + "\n" + (b2txt or "").strip() + "\n")
    if win and arms:
        try:
            q = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_pick_arm.py"),
                                "--since", win, "--min-rooms", str(min_rooms), "--strong-top", str(strong_top)],
                               cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=900)
            out += ("\n（下面是它们**自己那一役**的窗口 since=%s 的读数；"
                    "与上面当前窗口的读数**不可混读**）\n" % win) + (q.stdout or "").strip() + "\n"
        except Exception as e:
            out += "\n（B2 窗口读数不可得：%s）\n" % str(e)[:60]
    else:
        out += "\n（标记里没记窗口 ⇒ 请按该臂所在役的窗口手工跑 `var/_pick_arm.py --since <役窗口>`）\n"
    return out


def halves_cmds(since, strong_top, py=None, root=None):
    """★ R1549：两半 Pareto 的两条命令（§V.66 ② 的**真判据**）。纯函数，可单测。"""
    py = py or sys.executable
    root = root or ROOT
    low = os.path.join(root, "var", "_lowprio_run.py")
    return [
        ("half-A(胡牌率缺口两段分解)",
         [py, "-X", "utf8", low, "--", py, "-X", "utf8",
          os.path.join(root, "tools", "hu_gap_split.py"),
          "--dir", "recent", "--since", since, "--by-arm"]),
        ("half-B(同席头对头 TOP%d)" % strong_top,
         [py, "-X", "utf8", low, "--", py, "-X", "utf8",
          os.path.join(root, "var", "_seat_h2h.py"),
          "--since", since, "--by-arm", "--top", str(strong_top)]),
    ]


def halves_section(since, strong_top, runner=None):
    """★ R1549：把**两半 Pareto** 直接跑进提案里。

    为什么：R1501/R1505 已实测「主序列（强手房分/房）池化 SD≈129 ⇒ 80 房/臂 MDE≈41 分，
    而实测臂间差 22~38」⇒ `_pick_arm` **几乎必然报“不可区分”**，而它只会**叫人去跑**这两条 ——
    万一没跑，10/5 的人工选臂就是在**没有真正判据**的情况下做的。本函数把它跑完并贴进提案
    （只读、走 `_lowprio_run.py`）。
    """
    def _default(cmd):
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=1800)
    runner = runner or _default
    out = ("\n" + "=" * 78 + "\n"
           + "★ 两半 Pareto（R1501/R1505：**这才是真正判据**）\n"
           + "★ 为什么必须看：主序列（强手房分/房）池化 SD≈129 ⇒ 80 房/臂 MDE≈41 分，而实测臂间差 22~38\n"
           + "  ⇒ `_pick_arm` **几乎必然报“不可区分”**（≠没差别）；此时按 §V.66 ② 读这两张表：\n"
           + "  **两半都不差、且至少一半更好 ⇒ 候选胜**（half-A = 胡牌率缺口两段分解；half-B = 同席头对头）。\n"
           + "=" * 78 + "\n")
    for name, cmd in halves_cmds(since, strong_top):
        out += "\n---- %s ----\n$ %s\n" % (name, " ".join(cmd[1:]))
        try:
            p = runner(cmd)
            out += ((getattr(p, "stdout", "") or "") + (getattr(p, "stderr", "") or "")).strip() + "\n"
        except Exception as e:
            out += "（跑不动：%s）\n" % str(e)[:80]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rooms", type=int, default=30)
    ap.add_argument("--strong-top", type=int, default=32)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fallback-days", type=int, default=12,
                    help="无 .ab_mode（役已收口）时的回退窗口（天）；默认 12 覆盖整段战役")
    a = ap.parse_args()
    fallback = False
    if not os.path.exists(AB):
        # ★ R1450：役收口后 ab_ctl.stop 会**删** .ab_mode ⇒ 不能因此"不出提案"
        #   （否则 10/5 那天的选臂输入直接没了）。退回"最近 N 天"窗口，并**显式标注**是回退口径。
        fallback = True
        t0 = time.time() - a.fallback_days * 86400
        started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0))
        arms, baseline = [], ""
    else:
        cfg = json.loads(io.open(AB, encoding="utf-8-sig").read())
        if isinstance(cfg.get("arms"), list):
            arms = [str(x) for x in cfg["arms"]]
        else:
            arms = [x for x in (cfg.get("a"), cfg.get("b")) if x]
        started = str(cfg.get("started") or "")
        baseline = str((cfg.get("bundles") or arms[:1])[0])
    if not arms:
        # 回退口径下，臂集由台账推出（房数 >= min_rooms），供头行与分层读数使用
        cnt = {}
        try:
            for ln in io.open(LEDGER, encoding="utf-8", errors="ignore"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if d.get("status") != "finished" or (d.get("ts") or "") < started:
                    continue
                st = d.get("strategy")
                if st:
                    cnt[st] = cnt.get(st, 0) + 1
        except Exception:
            pass
        pairs = sorted(cnt.items(), key=lambda kv: -kv[1])
        arms = [k for k, v in pairs if v >= a.min_rooms]

    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_pick_arm.py"),
           "--since", started, "--min-rooms", str(a.min_rooms), "--strong-top", str(a.strong_top)]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    body = (p.stdout or "").strip()
    head = (
        "===== \u6700\u7ec8\u81c2\u9009\u62e9\u63d0\u6848 %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S")
        + "\u5f53\u524d\u6218\u5f79\u7a97\u53e3 started=%s\n\u53c2\u4e0e\u81c2\uff1a%s\n\u7b7e\u540d\u57fa\u7ebf\uff08bundles\uff09\uff1a%s\n" % (started, ", ".join(arms), baseline)
        # \u2605 R1564\uff1a\u56de\u9000\u53e3\u5f84\u5fc5\u987b**\u6253\u5728\u63d0\u6848\u6b63\u6587\u91cc**\u3002\u6700\u53ef\u80fd\u7684\u60c5\u5f62\u5c31\u662f\u201c\u5f79\u5df2\u6536\u53e3\u3001`.ab_mode` \u4e0d\u5728\u201d\uff0c
        #   \u800c\u90a3\u65f6\u7684\u7a97\u53e3\u662f\u201c\u6700\u8fd1 N \u5929\u201d\u2014\u2014\u5b83**\u8de8\u591a\u4e2a\u5f79\u6b21**\uff1a\u4e0d\u8bf4\u6e05\u5c31\u4f1a\u88ab\u8bfb\u6210\u201c\u67d0\u4e00\u5f79\u7684\u5224\u8bcd\u7a97\u53e3\u201d\u3002
        + (u"\u2605 **\u56de\u9000\u53e3\u5f84**\uff1a`.ab_mode` \u4e0d\u5728\uff08\u5f79\u5df2\u6536\u53e3\uff09\u21d2 \u672c\u63d0\u6848\u7528**\u6700\u8fd1 %d \u5929**\u7684\u53f0\u8d26\u7a97\u53e3\uff1b\n"
           u"  \u5b83**\u8de8\u591a\u4e2a\u5f79\u6b21**\u3001\u5404\u81c2\u623f\u6570\u4e0d\u7b49 \u21d2 \u53ea\u4f5c \xa7V.66 \u5e8f\u5217\u7684\u8f93\u5165\uff0c**\u4e0d\u53ef\u5f53\u67d0\u4e00\u5f79\u7684\u5224\u8bcd**\u3002\n" % a.fallback_days
           if fallback else u"")
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
    # ★ R1549：把两半 Pareto（真判据）直接跑进提案（只读，走 lowprio）
    text += halves_section(started, a.strong_top)
    _b2 = read_text(B2)
    if _b2:
        text += b2_section(_b2, a.min_rooms, a.strong_top)
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