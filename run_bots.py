"""四 AI 并发编排：同一测试房间跑 4 个 bot 实例（每人一个参赛令牌）。

用法：
    python run_bots.py <token1> <token2> <token3> <token4> [--server URL]
    python run_bots.py --file tokens.txt [--server URL]     # 每行一个令牌（空行/# 注释忽略）

- 每个令牌起一个独立 python run_bot.py 子进程（进程级隔离，日志各自落盘到 logs/）；
- 任一进程意外退出会按退出原因区分：正常结束（finish/淘汰/人工中断）不复位；
  异常/网络问题自动重启（最多 N 次）——测试房间 4 人齐了才会开局，缺员要补位；
- 同一测试房间 4 个名额 = 平台对局的完整一桌。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from bot.util import ensure_utf8, log, server_from_env

RESTART_MAX = 5          # 单个实例异常退出的最大重启次数
RESTART_DELAY = 3.0      # 重启间隔（秒）
TERMINAL_CODES = (0, 2, 130)  # 0=正常结束/淘汰 2=API 终错 130=人工中断


def read_tokens(path):
    tokens = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tokens.append(line.split()[0])
    return tokens


def main(argv=None):
    ensure_utf8()
    ap = argparse.ArgumentParser(description="四 AI 并发编排（同一测试房间 4 个令牌）")
    ap.add_argument("tokens", nargs="*", help="4 个参赛令牌；或用 --file 指定")
    ap.add_argument("--file", default="", help="令牌文件（每行一个）")
    ap.add_argument("--server", default=server_from_env(), help="服务器地址")
    ap.add_argument("--tid", default="", help="锦标赛 id（全局令牌自测路径用）")
    args = ap.parse_args(argv)

    tokens = args.tokens or read_tokens(args.file)
    if len(tokens) < 4:
        ap.error("需要至少 4 个令牌（当前 %d 个）：python run_bots.py t1 t2 t3 t4" % len(tokens))
    tokens = tokens[:4]

    os.makedirs("logs", exist_ok=True)
    log("启动 4 个 bot 实例（服务器: %s）", args.server)
    for i, t in enumerate(tokens, 1):
        log("  [%d] token=%s…%s", i, t[:8], t[-6:])

    procs = []
    restarts = [0] * len(tokens)
    try:
        while True:
            for i, t in enumerate(tokens):
                if i >= len(procs) or procs[i].poll() is not None:
                    # 检查该实例状态
                    if i < len(procs):
                        code = procs[i].returncode
                        log("实例[%d] 退出（code=%s）" % (i + 1, code))
                        if code in TERMINAL_CODES or restarts[i] >= RESTART_MAX:
                            if code not in TERMINAL_CODES:
                                log("实例[%d] 已达最大重启次数，放弃" % (i + 1))
                            procs[i] = None
                            continue
                        restarts[i] += 1
                        log("实例[%d] 异常退出，%ds 后重启（第 %d 次）…",
                            i + 1, RESTART_DELAY, restarts[i])
                        time.sleep(RESTART_DELAY)
                    # 启动（或重启）
                    cmd = [sys.executable, "run_bot.py", t]
                    if args.tid:
                        cmd.append(args.tid)
                    if args.server:
                        cmd.append("--server=%s" % args.server)
                    logf = open("logs/seat%d.log" % (i + 1), "a", encoding="utf-8")
                    procs[i] = subprocess.Popen(
                        cmd, stdout=logf, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    log("实例[%d] 已启动 pid=%s → logs/seat%d.log",
                        i + 1, procs[i].pid, i + 1)
                    continue    # 逐个启动后统一 sleep
            # 全部实例已退出（正常终态）→ 结束编排
            if all(p is None for p in procs):
                log("4 个实例均处于终态，编排退出。测试房间如需下一轮：再各 ready 一次。")
                return 0
            time.sleep(2)
    except KeyboardInterrupt:
        log("人工中断，终止全部实例…")
        for p in procs:
            if p and p.poll() is None:
                p.terminate()
        return 130


if __name__ == "__main__":
    sys.exit(main())
