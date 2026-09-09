"""tools/match_super —— 自动房监督循环（常驻：一房打完自动进下一房）。

- 每房：run_bot --match（notify + 决策录制自动开启；日志 logs/auto_<ts>.log）；
- 房终：GET /api/tournaments/{room}/ranking 立即归档（自动房结束后 ranking
  保留窗口很短，须跑完即抓）→ var/auto_ranking.jsonl（每行一房：room/时间/
  四家 rank/user_id/total_score/place_points/god_count/games_played）；
- 异常自愈：进程崩溃/房 404 瞬态 → 重试；目标房数达 --rooms N 后退出。

用法：python tools/match_super.py --rooms 8 [--strategy speedE]
停止：Stop-Process 或 Ctrl+C；全局令牌读 var/.global_token。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "var", ".global_token")
OUT_JSONL = os.path.join(ROOT, "var", "auto_ranking.jsonl")
BASE = "https://10.240.169.190:18080"


def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def fetch_ranking(room):
    """房终即时抓 ranking；失败返回 None（不阻塞循环）。"""
    import ssl
    import urllib.request
    token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(
            BASE + "/api/tournaments/" + room,
            headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            d = json.loads(r.read().decode("utf-8"))
        return (d.get("ranking") or [], d.get("status"))
    except Exception as e:
        return None


def one_room(strategy, log_path):
    """打一房：返回 room_id（从日志提取）或 None。"""
    token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    with open(log_path, "a", encoding="utf-8") as logf:
        p = subprocess.Popen(
            [sys.executable, "-X", "utf8", "run_bot.py", token, "--match",
             "--strategy", strategy, "--log", log_path],
            cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
        code = p.wait()
    # room id 从日志提取
    room = None
    try:
        for line in open(log_path, encoding="utf-8", errors="replace"):
            if "room=" in line:
                i = line.find("room=")
                room = line[i + 5:].split()[0].strip(",")
    except OSError:
        pass
    return room


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=6)
    ap.add_argument("--strategy", default="speedE")
    args = ap.parse_args()
    if not os.path.exists(TOKEN_FILE):
        raise SystemExit("缺 var/.global_token")
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    done = 0
    while done < args.rooms:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        logp = os.path.join(ROOT, "logs", "auto_%s.log" % stamp)
        print("%s 第 %d 房开始（strategy=%s log=%s）" %
              (ts(), done + 1, args.strategy, logp), flush=True)
        room = one_room(args.strategy, logp)
        if room:
            print("%s 房 %s 结束，抓 ranking…" % (ts(), room), flush=True)
            for attempt in range(4):
                res = fetch_ranking(room)
                if res is not None:
                    ranking, status = res
                    rec = {"ts": ts(), "room": room, "strategy": args.strategy,
                           "status": status, "ranking": ranking}
                    with open(OUT_JSONL, "a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print("%s ranking 归档 %d 条" % (ts(), len(ranking)),
                          flush=True)
                    break
                time.sleep(2)
            else:
                print("%s 房 %s ranking 抓取失败（保留窗口已过）" %
                      (ts(), room), flush=True)
        else:
            print("%s 房异常（无 room 日志），60s 后重试" % ts(), flush=True)
            time.sleep(60)
        done += 1
        if done < args.rooms:
            time.sleep(5)
    print("%s 完成 %d 房" % (ts(), done))


if __name__ == "__main__":
    sys.exit(main())
