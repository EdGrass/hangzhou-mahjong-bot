# -*- coding: utf-8 -*-
"""var/_final_event_ready.py —— 10/10 19:25 的 "T-5 保险"（**开关感知**）。

## 为什么要有它（原来是个单点故障）

正式赛入口原来只有 **18:50 一次** `_final_event_switch.py --go`；19:25 那台只跑 `_ready_1024.py`（POST /ready），
**不会重试上线**。若 18:50 因**瞬时**原因失败（门户抖动、网络、tid 解析临时歧义），T-40 分钟内没人补救，
比赛开始就**等于没参赛**。

## 行为（严格是原行为的超集）

1. `var/.official_mode` **已在位** ⇒ 行为与原来**完全一致**：只做 ready 幂等补发；
2. `.official_mode` **不在位** ⇒ 先**重试** `var/_final_event_switch.py --go`（同一套 fail-closed 门禁，
   **仍然不传 -AllowNotReady**），然后再补 ready；
3. 重试后**仍不在位** ⇒ 落 **`var/.EVENT_SWITCH_BLOCKED`** 并写日志（含**可照抄的人工命令**，
   含显式逃生阀 `-AllowNotReady` 的写法）—— 让 T-5 分钟的人一眼看到"差什么、该敲什么"。

## 红线

不改 `bot/`、不动任何进程、**不自动使用逃生阀**（`-AllowNotReady` 只写进提示，由人决定）；
只调现成脚本。用法：`python -X utf8 var/_final_event_ready.py [--dry-run]`。
"""
from __future__ import annotations
import argparse
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "var", "_final_event_ready.log")
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")
BLOCKED = os.path.join(ROOT, "var", ".EVENT_SWITCH_BLOCKED")
TOKEN = os.path.join(ROOT, "var", ".token_final_20261010")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def plan(official_mode_exists):
    """纯函数：→ ready_only | switch_then_ready。"""
    return "ready_only" if official_mode_exists else "switch_then_ready"


def run(cmd, timeout=1800):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=timeout)
    out = (p.stdout or b"") + (p.stderr or b"")
    for enc in ("utf-8", "gbk"):
        try:
            return p.returncode, out.decode(enc).strip()
        except Exception:
            continue
    return p.returncode, out.decode("utf-8", "replace").strip()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    py = sys.executable
    act = plan(os.path.exists(OFFICIAL))
    log("19:25 保险启动：official_mode=%s ⇒ %s" % (os.path.exists(OFFICIAL), act))
    if a.dry_run:
        print("（dry-run：将执行 %s，不落 BLOCKED）" % act)
        return 0
    if act == "switch_then_ready":
        rc, out = run([py, "-X", "utf8", os.path.join(ROOT, "var", "_final_event_switch.py"), "--go"])
        log("重试上线 rc=%s：%s" % (rc, out.splitlines()[-1][:160] if out else ""))
    rc2, out2 = run([py, "-X", "utf8", os.path.join(ROOT, "var", "_ready_1024.py"),
                     "--token-file", TOKEN])
    log("ready 补发 rc=%s：%s" % (rc2, out2.splitlines()[-1][:160] if out2 else ""))
    if not os.path.exists(OFFICIAL):
        cmd = ("powershell -NoProfile -File var/_switch_to_official.ps1 "
               "-Strategy <最终臂> -TokenFile %s -TournamentId <TID>") % TOKEN
        esc = cmd + " -AllowNotReady   # ← 仅在已确认该 BREAKING 无害时"
        # ★ R1463：补一条**规则门**的兜底 —— rules_guard 不匹配时 _switch_to_official.ps1 会直接 throw，
        #   而 -AllowNotReady **绕不过它**（它只管 preflight）。四测实测 YouCaiBiKao=false，但若正式赛改成 true，
        #   链上的臂（speedvaluebc/baotouv5/meldp45/bcmeldp45/bcvmeld/c151）**都没有 ycbk 孪生**，
        #   只有 speedvalueycbk 有 ⇒ 至少用它进场，好过不参赛。
        twin = (
            "# 若失败原因是 rules_guard（YouCaiBiKao ↔ 策略）：链上臂无 ycbk 孪生，唯一已注册的合规孪生是 speedvalueycbk：\n"
            "powershell -NoProfile -File var/_switch_to_official.ps1 -Strategy speedvalueycbk "
            "-TokenFile %s -TournamentId <TID>"
        ) % TOKEN
        try:
            with io.open(BLOCKED, "w", encoding="utf-8", newline="\n") as f:
                f.write("%s 仍未进入官方模式（19:25 重试后）\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                f.write("先看：var/_final_event_switch.log / var/_final_event_ready.log\n")
                f.write("人工命令：%s\n" % cmd)
                f.write("逃生阀（人决定）：%s\n" % esc)
                f.write(twin + "\n")
        except Exception:
            pass
        log("!! 仍未进入官方模式 ⇒ 已落 .EVENT_SWITCH_BLOCKED（含可照抄命令）")
        return 2
    if os.path.exists(BLOCKED):
        try:
            os.remove(BLOCKED)
            log("已清除 .EVENT_SWITCH_BLOCKED（保险完成）")
        except Exception:
            pass
    log("官方模式在位 ⇒ 保险完成（ready 已补发 rc=%s）" % rc2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
