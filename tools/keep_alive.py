"""tools/keep_alive —— 正式赛 bot 看门狗（防无人值守掉线）。

行为：拉起 run_bot.py 子进程；每 15s 检查：
- 子进程退出且锦标赛未到终态 → 自动重启（最多无限次，间隔 5s）；
- 锦标赛状态仅通过子进程日志推断，看门狗自身不做网络调用（避免双 token 竞态），
  只在子进程退出后重启——重启后 run_bot 幂等报名/到位/确认，语义安全。

用法：
    python tools/keep_alive.py <参赛令牌> [锦标赛id] [--strategy heuristicA] [--server URL]
退出：Ctrl+C 终止（会连带终止子进程）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "..")

from bot.util import ensure_utf8, log, server_from_env  # noqa: E402


def main():
    ensure_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("token", help="参赛令牌")
    ap.add_argument("tid", nargs="?", default="")
    ap.add_argument("--strategy", default="heuristicA")
    ap.add_argument("--server", default=server_from_env())
    args = ap.parse_args()

    log("看门狗启动：strategy=%s（Ctrl+C 退出并终止 bot）", args.strategy)
    while True:
        cmd = [sys.executable, "run_bot.py", args.token]
        if args.tid:
            cmd.append(args.tid)
        cmd += ["--strategy", args.strategy, "--server", args.server]
        log("启动 bot 子进程…")
        proc = subprocess.Popen(cmd, cwd=".")
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            log("人工中断：终止 bot 子进程")
            proc.terminate()
            return 130
        log("bot 子进程退出 code=%s，5s 后自动重启（幂等进场安全）", code)
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
