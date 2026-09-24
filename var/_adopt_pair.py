# -*- coding: utf-8 -*-
"""`var/_adopt_pair.py` —— **双候选役**的采用裁决 + 自动起下一役（BC/V 专用）。

## 为什么

`var/_bsegment.py` 起役时只注册**判词看护**（役 3 = `HangzhouMajVerdictWatch3bc/3v`），
**不注册采用看护**；而现成的 `HangzhouMajAdoptWatch` 只盯 `--label 役2`。
⇒ 役 3 判词落地后**没有任何东西会起役 4**，整条链会**静默停摆**（本机核对过：这是真缺口）。
役 3 判词约 2.5 天后落地，停摆一天就吃掉 10/7 前的余量。

## 判什么（全部来自已生效的预登记，本脚本不新增口径）

1. **候选各自的判词**（`_verdict_<label><suffix>.txt`）：最后一条 `★ 判定：` 以 **ADOPT** 开头才算 Δ；
2. **强手房否决**（役 3 预登记 §7/§8）：对每个 Δ 跑 `var/_strong_veto.py`（两层：≥1 / ≥2 名 top32，
   阈值 z ≤ −2.0 = §7 的「< −2×SE合并」）：
   - **VETO ⇒ 该候选按"不采用"处理**（§7.2 / §8：不作为正式赛选臂、继续测下一轴）；
   - **OK / UNKNOWN ⇒ 采用**（§7.3 / §8：样本不足"只记录，不据此翻转"）；
   - 其它 rc（工具异常）⇒ **无法判定 ⇒ 原地不动**（fail-closed，绝不猜）；
3. **四格 → 役 4 形态**（役 3 读卡 §3，逐字照抄）：BC✓ ⇒ 走 A 行；BC✗ 且 V✓ ⇒ 走 B 行；都不是 ⇒ NONE 行。

## 红线

- 两个候选的哨兵没齐 ⇒ **不动**；marker 已存在 ⇒ **幂等 no-op**；
- 任何读数缺失/异常 ⇒ **不动**（只记日志 + 落 marker 供人工看）；
- 真正干活只走现成 `var/_bsegment.py --go`（它自己：停驱动 → 等空档 → P0 → preflight → 切役 → 注册看护，
  任一步失败自己 return 2，**绝不强停对局**）；本脚本**不杀任何进程**。

用法：
    python -X utf8 var/_adopt_pair.py --dry-run      # 只打印裁决
    python -X utf8 var/_adopt_pair.py --go           # 真执行
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
LOG = os.path.join(ROOT, "var", "_adopt_pair.log")
AB = os.path.join(ROOT, "var", ".ab_mode")
LAST = "★ 判定："  # ★ 判定：


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def last_verdict(text):
    hit = None
    for ln in (text or "").splitlines():
        if LAST in ln:
            hit = ln.split(LAST, 1)[1].strip()
    return hit or ""


def is_adopt(line):
    return bool(re.match(r"ADOPT\s+[0-9A-Za-z_]+", (line or "").strip()))


def classify_candidate(verdict_line, veto_rc):
    """→ (adopted, reason)。adopted=None 表示**无法判定**（调用方必须原地不动）。

    veto_rc: 0=OK 2=UNKNOWN（都算采用）3=VETO（不采用）；其它 = 异常 ⇒ None。
    """
    if not is_adopt(verdict_line):
        return False, "判词非 ADOPT（%s）" % ((verdict_line or "（无）")[:28])
    if veto_rc == 3:
        return False, "强手房/决赛相似层显著劣 ⇒ 预登记不采用"
    if veto_rc in (0, 2):
        return True, "ADOPT 且未触发强手房否决（veto rc=%d）" % veto_rc
    return None, "强手房否决工具异常（rc=%s）⇒ 无法判定" % veto_rc


def pick_row(a_adopted, b_adopted):
    """四格 → 'a' / 'b' / 'none'（役 3 读卡 §3 逐字）。"""
    if a_adopted:
        return "a"
    if b_adopted:
        return "b"
    return "none"


def _read(path):
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def since_of():
    try:
        with io.open(AB, encoding="utf-8-sig") as f:
            return str(json.loads(f.read()).get("started") or "")
    except Exception:
        return ""


def run_veto(since, baseline, arm):
    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_strong_veto.py"),
           "--since", since, "--baseline", baseline, "--candidate", arm]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
    except Exception as e:
        return None, "无法运行强手房否决：%s" % str(e)[:60]
    tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-3:]
    return p.returncode, " ｜ ".join(tail)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役3")
    ap.add_argument("--baseline", default="speedvalue", help="本役基线（喂给强手房否决做对照）")
    ap.add_argument("--suffix-a", default="bc")
    ap.add_argument("--arm-a", default="speedvaluebc")
    ap.add_argument("--suffix-b", default="v")
    ap.add_argument("--arm-b", default="speedvaluebaotouv5")
    ap.add_argument("--since", default="")
    ap.add_argument("--next", default="役4")
    ap.add_argument("--row-a-base", default="speedvaluebc")
    ap.add_argument("--row-a-cands", default="speedvaluebcmeldp45")
    ap.add_argument("--row-b-base", default="speedvaluebaotouv5")
    ap.add_argument("--row-b-cands", default="speedvaluebaotouvmeld")
    ap.add_argument("--row-none-base", default="speedvalue")
    ap.add_argument("--row-none-cands", default="speedvaluemeldp45")
    ap.add_argument("--watch-mechanism", default="melds")
    ap.add_argument("--bsegment", default="var/_bsegment.py")
    ap.add_argument("--marker", default="")
    ap.add_argument("--timeout-min", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)

    marker = a.marker or os.path.join(ROOT, "var", ".adopted_pair_%s" % a.label)
    if os.path.exists(marker):
        log("已裁决过（%s 存在）⇒ no-op" % os.path.basename(marker))
        return 0

    since = a.since or since_of()
    rows, undecided = [], False
    for suf, arm in ((a.suffix_a, a.arm_a), (a.suffix_b, a.arm_b)):
        sent = os.path.join(ROOT, "var", ".verdict_done_%s%s" % (a.label, suf))
        if not os.path.exists(sent):
            log("%s：判词未决定性（缺 %s）⇒ 不动" % (arm, os.path.basename(sent)))
            return 0
        line = last_verdict(_read(os.path.join(ROOT, "var", "_verdict_%s%s.txt" % (a.label, suf))))
        rc, info = (None, "（非 ADOPT，未跑否决）")
        if is_adopt(line):
            if not since:
                rc, info = None, "拿不到本役起点（.ab_mode.started）"
            else:
                rc, info = run_veto(since, a.baseline, arm)
        adopted, why = classify_candidate(line, rc)
        log("%s：判词=「%s」｜%s｜%s" % (arm, line[:40], why, info))
        if adopted is None:
            undecided = True
        rows.append((arm, adopted))
    if undecided:
        log("!! 有候选无法判定 ⇒ 原地不动（需人工看上面几行）")
        return 2

    row = pick_row(rows[0][1], rows[1][1])
    base, cands = {
        "a": (a.row_a_base, a.row_a_cands),
        "b": (a.row_b_base, a.row_b_cands),
        "none": (a.row_none_base, a.row_none_cands),
    }[row]
    log("四格裁决：BC=%s / V=%s ⇒ 走 %s 行 ⇒ 役 4 = %s + %s"
        % (rows[0][1], rows[1][1], row.upper(), base, cands))

    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, a.bsegment), "--go",
           "--label", a.next, "--baseline", base, "--candidates", cands,
           "--watch-mechanism", a.watch_mechanism]
    if a.dry_run or not a.go:
        log("(dry-run) 将起下一役：%s" % " ".join(cmd))
        print("（未加 --go：只打印，不执行）")
        return 0
    log("起下一役：%s" % " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=a.timeout_min * 60)
    except subprocess.TimeoutExpired:
        log("!! B 段超时（%d 分钟）⇒ 人工检查（不对任何进程下手）" % a.timeout_min)
        return 2
    tail = "\n".join((p.stdout or "").strip().splitlines()[-6:])
    log("B 段 rc=%s：\n%s" % (p.returncode, tail))
    if p.returncode != 0:
        return p.returncode
    try:
        with io.open(marker, "w", encoding="utf-8") as f:
            f.write("%s row=%s base=%s cands=%s\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), row, base, cands))
    except Exception as e:
        log("⚠ 写 marker 失败：%s" % str(e)[:60])
    log("★ 已起 %s（基线 %s，候选 %s）" % (a.next, base, cands))
    return 0


if __name__ == "__main__":
    sys.exit(main())
