# -*- coding: utf-8 -*-
"""`var/_adopt_when_ready.py` —— 判词落地后**按预登记规则自动执行 B 段**（采用 + 起下一役）。

## 为什么

用户 2026-09-24 明确授权「都做 + 你自己想办法」（§V.160）。役 2 判词预计 09-25 凌晨落地；
若等人到场再执行，役 3 的起役窗口要白等几小时 —— 而每个役只剩约 2 天。
本脚本把「判词 → 采用 → 切役 3 → 注册看护」变成无人值守，**但只在判词明确 ADOPT 时动作**。

## 规则（事先写死，除 --force 外不可绕过）

1. 必须存在 sentinel `var/.verdict_done_<label>` —— 它是「判词决定性」的标志
   （`_verdict_watch.py` R1304：UNDECIDED/房数不足/覆盖不够 **不写** sentinel）；
2. 读判词文件，取**最后一条** `★ 判定：` 行；**该行必须以 `ADOPT` 开头**才执行；
3. 其余一切（REJECT / UNDECIDED / REFUSE / 无判词 / 文件缺 / 读不出）⇒ **只写日志，不碰任何进程**；
4. 幂等：执行成功后写 `var/.adopted_<label>`，此后直接退出（每 10 分钟调用也只是毫秒级 no-op）；
5. 真正干活只走既有 `_bsegment.py --go`（它自己：停驱动 → 等空档 → P0 补丁 → preflight → 切役 → 注册看护；
   任何一步失败它自己 return 2，**绝不强停对局**）。

## 红线

本脚本自身不杀进程、不改 `bot/`、不动台账；只在规则 1+2 同时满足时调用既有 B 段脚本。
失败路径一律「什么都不做 + 记日志」。

用法：
    python -X utf8 var/_adopt_when_ready.py --label 役2 --dry-run
    python -X utf8 var/_adopt_when_ready.py --label 役2
"""
from __future__ import annotations
import argparse
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "var", "_adopt_when_ready.log")


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass
    print(msg)


def last_verdict_line(text):
    """判词里最后一条 `★ 判定：` 行（没有就返回 None）。"""
    hit = None
    for ln in (text or "").splitlines():
        if "★ 判定：" in ln:
            hit = ln.split("★ 判定：", 1)[1].strip()
    return hit


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役2")
    ap.add_argument("--verdict", default="")
    ap.add_argument("--sentinel", default="")
    ap.add_argument("--marker", default="")
    ap.add_argument("--baseline", default="speedvalue")
    ap.add_argument("--candidates", default="speedvaluebc,speedvaluebaotouv5")
    ap.add_argument("--bsegment", default="var/_bsegment.py")
    ap.add_argument("--timeout-min", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="调试用：跳过规则 1+2（默认关闭）")
    a = ap.parse_args(argv)

    verdict = a.verdict or os.path.join(ROOT, "var", "_verdict_%s.txt" % a.label)
    sentinel = a.sentinel or os.path.join(ROOT, "var", ".verdict_done_%s" % a.label)
    marker = a.marker or os.path.join(ROOT, "var", ".adopted_%s" % a.label)

    if os.path.exists(marker):
        print("已采用过（%s 存在）⇒ no-op" % marker)
        return 0
    if not a.force:
        if not os.path.exists(sentinel):
            print("判词未决定性（缺 %s）⇒ 不动" % os.path.basename(sentinel))
            return 0
        try:
            txt = io.open(verdict, encoding="utf-8-sig", errors="replace").read()
        except Exception as e:
            log("!! 读判词失败（%s）⇒ 不动" % str(e)[:80])
            return 0
        line = last_verdict_line(txt)
        if not line or not line.upper().startswith("ADOPT"):
            log("判词非 ADOPT（%s）⇒ 不动" % (line or "无判词行"))
            return 0

    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, a.bsegment), "--go",
           "--baseline", a.baseline, "--candidates", a.candidates]
    log("★ 判词 ADOPT ⇒ 执行 B 段：%s" % " ".join(cmd))
    if a.dry_run:
        print("（dry-run：未执行）")
        return 0
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=a.timeout_min * 60)
    except subprocess.TimeoutExpired:
        log("!! B 段超时（%d 分钟）⇒ 人工检查（不对任何进程下手）" % a.timeout_min)
        return 2
    rc = p.returncode
    tail = "\n".join((p.stdout or "").strip().splitlines()[-6:])
    log("B 段 rc=%s：\n%s" % (rc, tail))
    if rc == 0:
        try:
            with io.open(marker, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " adopted\n")
        except Exception as e:
            log("⚠ 写 marker 失败：%s" % str(e)[:60])
    return rc


if __name__ == "__main__":
    sys.exit(main())