# -*- coding: utf-8 -*-
"""`var/_apply_p0_404.py` —— **P0 修复的一键落地器**（默认 dry-run；`--go` 才写盘）。

## 修什么（R1221/R1223）

平台 v35（2026-09-23 BREAKING）：`404 TOURNAMENT_GONE`（**房暂时不可达 ⇒ 应重试**）与
`TOURNAMENT_NOT_FOUND`（房不存在 ⇒ 应放弃）**共用 404**。我们旧实现只按"持续 >120s"就退出
⇒ 已把 **29 次 GONE** 误判为"房已删"（含官方 run 12 次退出/重启抖动）。

两处改动：
1. `bot/protocol.py`：404 分支按 `body.code` 分流（NOT_FOUND ⇒ 退出；**GONE ⇒ 不限时重试**；其它 ⇒ 保守重试）；
2. `bot/__init__.py`：`GUIDE_VERSION_KNOWN 34 → 35`。

## 为什么单独做个落地器

两个文件的**行尾不一致**（`protocol.py` 为 LF、`__init__.py` 为 CRLF）⇒ 统一 diff 补丁会因行尾不匹配而 apply 失败。
本器**按字节做精确替换**，因此行尾、编码都不受影响；并自带 `--check` 干跑。

## 用法（**只在役次切换窗口执行**；红线 3 禁止在跑役期间改 bot/）

    python -X utf8 var/_apply_p0_404.py --check      # 只检查（不动文件）
    python -X utf8 var/_apply_p0_404.py --go         # 真写盘 + 自动跑 --smoke 验收
"""
from __future__ import annotations
import argparse, io, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROT = os.path.join(ROOT, "bot", "protocol.py")
INIT = os.path.join(ROOT, "bot", "__init__.py")

OLD_404 = b"""            if e.status == 404:
                # \xe6\x9c\x8d\xe5\x8a\xa1\xe5\x99\xa8\xe9\x87\x8d\xe5\x90\xaf\xe7\x9e\xac\xe6\x80\x81"""
NEW_404 = """            if e.status == 404:
                # \u2605 v35\uff082026-09-23 BREAKING\uff09\uff1a404 \u5206\u4e24\u79cd\uff0c**\u5fc5\u987b\u770b body \u7684 code**
                #   TOURNAMENT_NOT_FOUND = \u623f\u4e0d\u5b58\u5728 \u21d2 \u653e\u5f03\uff08\u9000\u51fa\uff09
                #   TOURNAMENT_GONE      = \u623f\u6682\u65f6\u4e0d\u53ef\u8fbe \u21d2 **\u5fc5\u987b\u91cd\u8bd5**\uff08\u4e0d\u5f97\u6309\u6301\u7eed\u65f6\u95f4\u5224\u6b7b\uff09
                #   \u5176\u5b83/\u65e0\u6cd5\u89e3\u6790\u7684 code \u21d2 \u4fdd\u5b88\u5f53\u4f5c\u77ac\u6001\u91cd\u8bd5\uff08\u53ea\u8bb0\u65e5\u5fd7\uff09\u3002
                #   \u80cc\u666f\uff08R1221/R1223\uff09\uff1a\u65e7\u5b9e\u73b0\u53ea\u770b"404 \u6301\u7eed >120s"\u21d2 \u5df2\u628a 29 \u6b21 GONE
                #   \u8bef\u5224\u6210"\u623f\u5df2\u5220"\u800c\u9000\u51fa\uff08\u542b\u5b98\u65b9 run 12 \u6b21\u9000\u51fa/\u91cd\u542f\u6296\u52a8\uff09\u3002
                code = (e.code or "")
                if code == "TOURNAMENT_NOT_FOUND":
                    log("\u9526\u6807\u8d5b\u8be6\u60c5 404 TOURNAMENT_NOT_FOUND \u2014\u2014 \u623f\u95f4\u4e0d\u5b58\u5728\uff0c\u9000\u51fa")
                    raise
                now404 = time.time()
                if last_404_at == 0.0:
                    last_404_at = now404
                log("\u9526\u6807\u8d5b\u8be6\u60c5 404 %s\uff08\u6682\u65f6\u4e0d\u53ef\u8fbe\uff0c\u5df2\u6301\u7eed %.0fs\uff09\uff0c2s \u540e\u91cd\u8bd5\u2026",
                    code or "(\u65e0 code)", now404 - last_404_at)
                time.sleep(2)
                continue
"""


def _replace_bytes(path, old_start, old_end_marker, new_bytes):
    """在 [old_start, old_end_marker] 之间整段替换（按字节，保住原有行尾）。"""
    b = open(path, "rb").read()
    i = b.find(old_start)
    if i < 0:
        return None, "未找到起始锚点"
    j = b.find(old_end_marker, i)
    if j < 0:
        return None, "未找到结束锚点"
    j += len(old_end_marker)
    return b[:i] + new_bytes + b[j:], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="真写盘（默认只检查）")
    ap.add_argument("--check", action="store_true", help="只检查（默认行为，显式给出便于脚本化）")
    a = ap.parse_args()

    # ---- (1) protocol.py：整段替换 404 分支 ----
    old_start = b"            if e.status == 404:"
    old_end = b"                time.sleep(2)\n                continue\n"
    new_404 = NEW_404.replace("\n", "\r\n").encode("utf-8") if b"\r\n" in open(PROT, "rb").read() else NEW_404.encode("utf-8")
    nb, err = _replace_bytes(PROT, old_start, old_end, new_404)
    if err:
        print("❌ protocol.py：%s" % err)
        return 2
    print("✓ protocol.py：404 分支可替换（%d → %d 字节）" % (len(open(PROT, "rb").read()), len(nb)))

    # ---- (2) __init__.py：版本号 ----
    ib = open(INIT, "rb").read()
    nl = b"\r\n" if b"\r\n" in ib else b"\n"
    old_ver = b"GUIDE_VERSION_KNOWN = 34"
    if old_ver not in ib:
        print("❌ bot/__init__.py：未找到 `GUIDE_VERSION_KNOWN = 34`（可能已改过）")
        return 2
    ib2 = ib.replace(old_ver, b"GUIDE_VERSION_KNOWN = 35", 1)
    print("✓ bot/__init__.py：版本号 34 → 35 可替换")

    if not a.go:
        print("（--check 通过；加 --go 才写盘）")
        return 0

    open(PROT, "wb").write(nb)
    open(INIT, "wb").write(ib2)
    print("已写盘。接下来自动跑验收：")
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "run_bot.py"), "--smoke"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [x for x in ((r.stdout or "") + (r.stderr or "")).splitlines() if x.strip()][-3:]
    for t in tail:
        print("   ", t)
    print("验收：%s" % ("✅ --smoke 通过" if "全部通过" in (r.stdout or "") else "⚠ 请看上面输出"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
