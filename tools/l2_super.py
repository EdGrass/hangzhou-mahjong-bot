"""tools/l2_super —— L2 真机同桌主管（多会话自动续跑，直到用户叫停/目标局数）。

背景：服务器约 70-90 分钟重启一次，重启后测试房被清理（404）→ 单会话
只能积累 ~50-60 场。本主管：
- ctypes 探活（不派生子进程，规避沙箱管道限制）；
- 房死（4 bot 全退）→ 用 var/.portal_cookie 新建测试房（M=1 rounds=1）
  并以 青龙/白虎=speedx1、朱雀/玄武=speedE 重派 4 bot（同日志文件续写）；
- 会话记录 var/l2/sessions.jsonl；审计 tools/l2_audit.py 跨会话累积（gid 唯一）。

用法：python tools/l2_super.py   （Start-Process 脱离会话；日志 var/l2/super.log）
停止：Stop-Process -Id <super.pid>（随后手动关房 room_ctl close <room>）
"""
from __future__ import annotations

import ctypes
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "var", "l2")
COOKIE_FILE = os.path.join(ROOT, "var", ".portal_cookie")
ROOM_FILE = os.path.join(STATE, "room.json")
PIDS_FILE = os.path.join(STATE, "pids.json")
SESSIONS_FILE = os.path.join(STATE, "sessions.jsonl")
BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()
# 服务器返回中文席位名 → 拼音日志名（与 l2_audit 的 l2x1_*.log glob 一致）
PINYIN = {"青龙": "qinglong", "白虎": "baihu",
          "朱雀": "zhuque", "玄武": "xuanwu"}
# 席位 → 策略 的默认硬编码映射（未设 HM_SEAT_STRATEGIES 时向后兼容回退）：
# 注意 speedx1/speedx2 已随清理轮删除——默认改为全 speedE（安全对称基线），
# A/B 会话一律通过 HM_SEAT_STRATEGIES 显式指定（如 speedh×2 + speedE×2）。
DEFAULT_SEAT_STRATEGY = {"青龙": "speedE", "白虎": "speedE",
                         "朱雀": "speedE", "玄武": "speedE"}


def ts():
    return time.strftime("%H:%M:%S")


def seat_strategy_map():
    """席位 → 策略 映射：优先读环境变量 HM_SEAT_STRATEGIES（JSON），
    未设置则回退默认硬编码（向后兼容）。"""
    raw = os.environ.get("HM_SEAT_STRATEGIES")
    if not raw:
        return dict(DEFAULT_SEAT_STRATEGY)
    try:
        m = json.loads(raw)
        return {str(k): str(v) for k, v in m.items()}
    except (ValueError, TypeError):
        # 环境变量非法 → 回退默认，不炸房
        return dict(DEFAULT_SEAT_STRATEGY)


def seat_strategy(seat):
    """按席位名返回策略；未知席位/未配置时兜底 speedE。"""
    return seat_strategy_map().get(seat, "speedE")


def alive(pid):
    """ctypes OpenProcess 探活（无子进程/管道）。"""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                           False, int(pid))
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    return False


def cookie():
    with open(COOKIE_FILE, encoding="utf-8-sig") as f:   # 容忍 BOM
        return f.read().strip()


def create_room():
    body = json.dumps({"M": 1, "Rounds": 1, "name": "l2-x1-vs-E"}).encode()
    req = urllib.request.Request(BASE + "/portal/api/test-rooms", data=body,
                                 headers={"Cookie": cookie(),
                                          "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        d = json.loads(r.read().decode("utf-8"))
    specs = []
    strat = seat_strategy_map()
    for p in d.get("players", []):
        n = p.get("name", "")
        specs.append({"name": PINYIN.get(n, n), "tok": p["token"],
                      "s": strat.get(n, "speedE")})
    if len(specs) != 4:
        raise RuntimeError("建房玩家数异常: %s" % (specs,))
    return d["room_id"], specs


def spawn(spec):
    logf = open(os.path.join(ROOT, "logs", "l2x1_%s.log" % spec["name"]),
                "a", encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, "-X", "utf8", "run_bot.py", spec["tok"],
         "--strategy", spec["s"], "--log", "logs/l2x1_%s.log" % spec["name"]],
        cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
    spec["pid"] = child.pid
    return spec


def new_session():
    print("%s create room..." % ts(), flush=True)
    room, specs = create_room()
    for s in specs:
        spawn(s)
    state = {"room": room, "created_at": ts(), "specs": specs}
    with open(ROOM_FILE, "w", encoding="utf-8") as f:
        json.dump({"room": room, "start": ts(), "specs": specs}, f,
                  ensure_ascii=False, indent=1)
    with open(PIDS_FILE, "w", encoding="utf-8") as f:
        json.dump([{"name": s["name"], "strategy": s["s"], "pid": s["pid"]}
                   for s in specs], f, ensure_ascii=False, indent=1)
    with open(SESSIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(state, ensure_ascii=False) + "\n")
    print("%s session=%s bots=%s" % (ts(), room,
                                     [(s["name"], s["s"]) for s in specs]),
          flush=True)


def main():
    os.makedirs(STATE, exist_ok=True)
    if not os.path.exists(COOKIE_FILE):
        print("%s 缺 var/.portal_cookie" % ts(), flush=True)
        return 1
    while True:
        try:
            new_session()
            break
        except Exception as e:
            print("%s 初始建房失败: %s（30s 后重试）" % (ts(), e), flush=True)
            time.sleep(30)
    while True:
        time.sleep(15)
        try:
            with open(PIDS_FILE, encoding="utf-8") as f:
                specs = json.load(f)
        except (OSError, ValueError):
            continue
        dead = [s for s in specs if not alive(s.get("pid"))]
        if len(dead) == 4:
            print("%s 会话全退（房大概率被清理）→ 重建" % ts(), flush=True)
            try:
                new_session()
            except Exception as e:
                print("%s 建房失败: %s（60s 后重试）" % (ts(), e), flush=True)
                time.sleep(60)
        elif dead:
            for s in dead:
                print("%s %s down(pid=%s) -> respawn" % (
                    ts(), s["name"], s.get("pid")), flush=True)
                spawn(s)
            with open(PIDS_FILE, "w", encoding="utf-8") as f:
                json.dump(specs, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
