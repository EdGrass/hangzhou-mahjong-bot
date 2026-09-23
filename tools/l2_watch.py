"""tools/l2_watch —— L2 真机同桌 bot 看门狗（崩溃自动重启，保持 per-bot 日志）。

读 var/l2/pids.json（含 name/tok/strategy/pid），每 20s 检查进程存活，
死亡则重启 `run_bot.py <tok> --strategy <s> --log logs/l2x1_<name>.log`
（run_bot --log 为 append 模式，重启后审计日志连续），并回写 pids.json。
人工停止：Stop-Process -Id <watch.pid>。

用法：python tools/l2_watch.py     （建议 Start-Process 脱离会话运行）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PID_FILE = os.path.join(ROOT, "var", "l2", "pids.json")
ROOM_FILE = os.path.join(ROOT, "var", "l2", "room.json")


def _ts():
    return time.strftime("%H:%M:%S")


def _alive(pid):
    try:
        r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV"],
                           capture_output=True, text=True, timeout=15)
        return str(pid) in r.stdout
    except Exception:
        return True              # 查询失败时保守视为存活，避免双开


def main():
    with open(PID_FILE, encoding="utf-8") as f:
        specs = json.load(f)
    with open(ROOM_FILE, encoding="utf-8") as f:
        room = json.load(f)
    print("%s watcher start: room=%s bots=%s" % (
        _ts(), room["room"], [s["name"] for s in specs]), flush=True)
    while True:
        for s in specs:
            if not _alive(s["pid"]):
                print("%s %s down(pid=%s) -> restart" % (
                    _ts(), s["name"], s["pid"]), flush=True)
                logf = open(os.path.join(ROOT, "logs",
                                         "l2x1_%s.log" % s["name"]), "a",
                            encoding="utf-8")
                child = subprocess.Popen(
                    [sys.executable, "-X", "utf8", "run_bot.py", s["tok"],
                     "--strategy", s["s"], "--log", "logs/l2x1_%s.log" % s["name"]],
                    cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
                s["pid"] = child.pid
                with open(PID_FILE, "w", encoding="utf-8") as f:
                    json.dump(specs, f, ensure_ascii=False, indent=1)
                time.sleep(3)
        time.sleep(20)


if __name__ == "__main__":
    main()
