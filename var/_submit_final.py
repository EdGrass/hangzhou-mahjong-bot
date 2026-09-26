# -*- coding: utf-8 -*-
"""var/_submit_final.py —— 10/8 提交（把操作卡里那三步变成一条自动链，并加门禁与收据）。

## 为什么

操作卡（final-switch-card-20261007.md）的"最后一步"是：
_prepare_submission.ps1（只检查）→ -Go（add -f + commit）→ git push。
这是**唯一一个硬截止（10/8 12:00）且原先全靠人工**的环节；错过 = 没交上。
本机已验证：git push --dry-run 在**非交互**（GIT_TERMINAL_PROMPT=0）下成功 ⇒ 推送不需要人到场。

## 门禁（fail-closed，任一条不过就不提交）

1. var/.final_submitted 已存在 ⇒ 幂等 no-op；
2. _prepare_submission.ps1（只检查）rc 必须为 0 —— 它已覆盖：交付物、4 个模型文件、69 个运行期脚本、
   泄密门（无 64 位令牌串 / 无纯令牌小文件）、文案与代码版本一致、git 追踪完整性；
3. 提交后必须校验：工作区干净 **且** 本地 == origin/main（即验收第 6 项口径）。

## 红线

不改 bot/、不动任何进程、不删任何东西；只调**现成的** _prepare_submission.ps1 与 git。

用法：
    python -X utf8 var/_submit_final.py --dry-run   # 只走到门禁，不提交
    python -X utf8 var/_submit_final.py --go        # 真提交 + 推送
"""
from __future__ import annotations
import argparse
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
LOG = os.path.join(ROOT, "var", "_submit_final.log")
MARKER = os.path.join(ROOT, "var", ".final_submitted")
NOT_READY = os.path.join(ROOT, "var", ".FINAL_NOT_READY")   # ★ R1569：失败要有人读（心跳 0g 会转述）
OUT = os.path.join(ROOT, "var", "_submit_final.out")
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
COMMIT_MSG = "chore(R1448): 10/8 提交物（_prepare_submission -Go 自动提交）"


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def gate(check_rc, marker_exists):
    """纯函数：→ (noop | abort | go, 原因)。

    门禁只认 _prepare_submission.ps1（只检查）的 rc：它内部已含泄密门/模型/脚本/文案一致性。
    """
    if marker_exists:
        return "noop", "已提交过（.final_submitted 存在）"
    if check_rc != 0:
        return "abort", "提交物检查 rc=%s（不为 0 ⇒ 不提交；先看 _prepare_submission 的输出）" % check_rc
    return "go", "门禁通过（提交物检查 rc=0）"


def fail_mark(reason, path=None):
    """★ R1569：提交失败必须**留一个有人读的标记**。

    为什么：`_submit_final` 失败时只 `log()` + `return 2` ⇒ 而心跳 0g 只认
    `.final_submitted`（**成功**标记）⇒ **失败是静默的**，而这条链的截止是 **10/8 12:00**。
    复用已有的 `.FINAL_NOT_READY`（总账里已登记，心跳 0g 已会转述）—— 不新造标记名。
    """
    p = path or NOT_READY
    try:
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(u"%s 10/8 提交失败：%s\n"
                    u"  ⇒ **10/8 12:00 前必须人工完成**（该项有一次 11:00 自动重试）："
                    u"`python -X utf8 var/_submit_final.py --go`\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), reason))
        return True
    except Exception:
        return False


def clear_fail_mark(path=None):
    """仅清**我们自己写的**那行（避免误删 `_final_ready_check` 的内容）。"""
    p = path or NOT_READY
    try:
        s = io.open(p, encoding="utf-8-sig", errors="replace").read()
        if u"10/8 提交失败" in s:
            os.remove(p)
            return True
    except Exception:
        pass
    return False


def _dec(b):
    """字节 → 文本。

    ★ 为什么要兜底：任务上下文里 pythonw 抓到的是 Windows PowerShell 5.1 的**ANSI/GBK** 输出，
    按 UTF-8 解会变成一串 U+FFFD（本机实测：日志里中文全乱码）。门禁用的是 rc、功能不受影响，
    但日志是审计轨迹 ⇒ 依次试 utf-8 / gbk，最后才用 replace。
    """
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", "replace")


def run(cmd, timeout=900, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=timeout, env=e)
    out = _dec((p.stdout or b"") + (p.stderr or b"")).strip()
    return p.returncode, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    import _ps  # PowerShell 解析器（R1379）：任务环境无 pwsh 也能退回 powershell.exe
    ps = _ps.exe()

    rc, out = run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1])
    tail = (out.splitlines() or [""])[-1][:120]
    log("提交物检查 rc=%s：%s" % (rc, tail))
    act, why = gate(rc, os.path.exists(MARKER))
    log("门禁判定：%s（%s）" % (act.upper(), why))
    if act != "go":
        try:
            with io.open(OUT, "w", encoding="utf-8", newline="") as f:
                f.write("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), act.upper()))
        except Exception:
            pass
        return 0 if act == "noop" else 2
    if a.dry_run or not a.go:
        print("（未加 --go：只走到门禁，不提交）")
        return 0

    rc2, out2 = run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, "-Go"])
    log("准备提交物（-Go）rc=%s" % rc2)
    if rc2 != 0:
        log("!! -Go 失败 ⇒ 不推送：%s" % out2[-300:])
        fail_mark(u"-Go 失败：%s" % out2[-200:])
        return 2
    dirty = run(["git", "status", "--porcelain"])[1]
    if dirty.strip():
        run(["git", "add", "-A"])
        rc_c, out_c = run(["git", "-c", "core.quotepath=false", "commit", "-q", "-m", COMMIT_MSG])
        log("commit rc=%s %s" % (rc_c, out_c[-160:]))
    rc4, out4 = run(["git", "push", "origin", "HEAD:main"], timeout=600,
                    env={"GIT_TERMINAL_PROMPT": "0"})
    log("push rc=%s %s" % (rc4, out4[-200:]))
    if rc4 != 0:
        log("!! 推送失败 ⇒ 未写 .final_submitted（需人工）")
        fail_mark(u"推送失败 rc=%s" % rc4)
        return 2
    run(["git", "fetch", "origin"], timeout=300)
    lr = run(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])[1].strip()
    clean = not run(["git", "status", "--porcelain"])[1].strip()
    in_sync = (lr.split() == ["0", "0"]) if lr else False
    log("提交后校验：工作区干净=%s 本地==origin/main=%s（%s）" % (clean, in_sync, lr))
    if not (clean and in_sync):
        log("!! 提交后校验未过 ⇒ 不写 marker（需人工看上面）")
        fail_mark(u"提交后校验未过（%s）" % lr)
        return 2
    try:
        with io.open(MARKER, "w", encoding="utf-8", newline="") as f:
            f.write("%s submitted（push ok，本地==origin/main）" % time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        log("⚠ 写 marker 失败：%s" % str(e)[:60])
    clear_fail_mark()
    log("★ 已提交并推送：HEAD 与 origin/main 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
