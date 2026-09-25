# -*- coding: utf-8 -*-
"""`var/_lowprio_run.py` —— **离线重活必须以低于正常优先级运行**（A/B 期间硬纪律的落地工具）。

## 为什么（R1182）

对 9/23–9/24 的**提交延迟**做审计（1,485 个 `sub_ms` 样本）：
    p50=15.6ms  p90=26.4ms  **p99=2,827ms**  max=5,600ms
    ≥500ms **30 次（2.0%）**；≥1s **28 次（1.9%）**；≥2s **19 次**
且**慢尖峰与"本机跑离线重活的时间窗"高度重合**（00:57 起跑全套单测 → 00:57:41 两条 2.87s；
01:25 跑 meld_opportunity → 01:25:16 1.01s；01:39 跑 by-start 全量 → 01:39:41 **4.01s**），
而**没有任何本地负载时** p50 只有 15ms 级。后果不是"看起来慢"，而是**真的丢动作**：
同一批日志里 `409（已失效）`共 6,111 次，其中 **discard 55 次（27 次 ≥300ms）**、chi 390 / peng 210。

⇒ 纪律：**A/B 期间离线重活（单测全量、全语料分析、足迹/复盘扫描）必须**
**①低于正常优先级** 且 **②同一时刻只跑一个**。

## 用法

    python -X utf8 var/_lowprio_run.py -- <命令> [参数...]        # 前台，BelowNormal
    python -X utf8 var/_lowprio_run.py --detach --log out.txt -- <命令>   # 后台 + 写日志

实现：Windows 用 `psutil` 把自己（及子进程继承的优先级）设为 `BELOW_NORMAL_PRIORITY_CLASS`；
非 Windows 用 `os.nice(10)`。**不改变任何被调用程序的语义**（纯优先级包装）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def lower_self():
    """把自己降到 BelowNormal；返回实际生效的说明字符串。"""
    try:
        import psutil
        p = psutil.Process(os.getpid())
        if os.name == "nt":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            return "windows:BELOW_NORMAL"
        p.nice(10)
        return "posix:nice10"
    except Exception as e:                      # 降级失败不阻塞任务
        try:
            if os.name != "nt":
                os.nice(10)
                return "posix:nice10(fallback)"
        except Exception:
            pass
        return "noop(%s)" % e


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--detach", action="store_true", help="后台运行并立刻返回")
    ap.add_argument("--log", default="", help="--detach 时的 stdout/stderr 落盘路径")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = [x for x in a.cmd if x != "--"]
    if not cmd:
        print("用法：python -X utf8 var/_lowprio_run.py [--detach] [--log out.txt] -- <命令> ...")
        return 2

    def _spawn(detached):
        kwargs = {}
        if detached and a.log:
            fh = open(a.log, "ab")
            kwargs["stdout"] = fh
            kwargs["stderr"] = fh
        return subprocess.Popen(cmd, **kwargs)

    if a.detach:
        p = _spawn(True)
        try:
            import psutil
            psutil.Process(p.pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
        except Exception:
            pass
        print("已后台启动 pid=%d（%s）：%s" % (p.pid, lower_self(), " ".join(cmd)))
        return 0

    print("[lowprio] %s ⇒ %s" % (lower_self(), " ".join(cmd)), flush=True)
    # ★ R1536：**显式**把本进程的 stdout/stderr 交给子进程，不能只靠“句柄继承”。
    #   为什么（生产实测，不是洁癖）：计划任务用 **pythonw.exe** 起 `_mech_watch.py`，
    #   它再经本包装器跑 `_seat_h2h.py --by-arm`；只靠继承时**孙进程的输出会被丢掉** ——
    #   `_mech_watch.log` 连出两次 `!! V 机制读数（_seat_h2h）解析为空：rc=0 stdout=191 字`
    #   而那 191/176 字**正好只有本函数的 banner**（真表是 3600+ 字）⇒ V 轴的机制读数
    #   永远拿不到 ⇒ V 既判不出 PASS 也判不出 FAIL（只能 UNKNOWN）⇒ 若四格由 V 决定就停摆。
    #   本机 A/B 实证：pythonw 下“pythonw 孙进程”与“python 孙进程”**都会丢**（与 GUI 子系统无关），
    #   修后同一条命令能拿到完整表。
    kw = {}
    if sys.stdout is not None:
        kw["stdout"] = sys.stdout
    if sys.stderr is not None:
        kw["stderr"] = sys.stderr
    return subprocess.call(cmd, **kw)


if __name__ == "__main__":
    raise SystemExit(main())
