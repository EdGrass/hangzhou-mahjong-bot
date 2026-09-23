"""tools/match_super —— 自动房监督循环 v2（一房打完自动进下一房）。

v2 改进：supervisor 先 POST /api/match 预占一房拿到 room_id，再以
【全局令牌 + 显式 tid】跑 run_bot（不依赖日志提取 room——旧版日志句柄
双写异常时可致 0 字节，room 提取失败）。

每房流程：
1. /api/match → {room_id}（重试 429/网络）；
2. run_bot.py <tok> <room_id> --strategy S --log logs/auto_<ts>.log
   --record-replays var/replays/auto_<ts>/；
3. 房终：GET /api/tournaments/{room_id} ranking 即时归档
   var/auto_ranking.jsonl（自动房结束后 ranking 保留窗口短，跑完即抓）；
4. 崩溃自愈重试；--rooms N 房后退出。

用法：python tools/match_super.py --rooms 6 [--strategy speedE]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "var", ".global_token")
OUT_JSONL = os.path.join(ROOT, "var", "auto_ranking.jsonl")
BASE = os.environ.get("HM_SERVER", "").strip() or "http://127.0.0.1:8080"
REPLAY_ROOT = os.path.join(ROOT, "var", "replays")


def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _token():
    return open(TOKEN_FILE, encoding="utf-8").read().strip()


def api_match():
    """POST /api/match 预占自动房 → room_id。失败抛异常（由调用方重试）。"""
    import ssl
    import urllib.request
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        BASE + "/api/match", data=b"{}",
        headers={"Authorization": "Bearer " + _token(),
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        # v29：功能开关关闭 = 永久条件，绝不重试（指南明确「不要重试」）
        if e.code == 403 and "FEATURE_DISABLED" in body:
            raise SystemExit(
                "自由匹配已被管理端关闭（403 FEATURE_DISABLED，永久条件）——"
                "停止而非重试。可 GET /portal/api/features 预检。")
        raise
    room = d.get("room_id") or d.get("tournament_id") or ""
    if not room:
        raise RuntimeError("match 无 room_id: %s" % str(d)[:200])
    return room


def fetch_ranking(room):
    import ssl
    import urllib.request
    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(
            BASE + "/api/tournaments/" + room,
            headers={"Authorization": "Bearer " + _token()})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("ranking") or [], d.get("status")
    except Exception:
        return None


def one_room(strategy, stamp):
    room = api_match()
    logp = os.path.join(ROOT, "logs", "auto_%s.log" % stamp)
    rec_dir = os.path.join(REPLAY_ROOT, "auto_%s" % stamp)
    argv = [sys.executable, "-X", "utf8", "run_bot.py", _token(), room,
            "--strategy", strategy, "--log", logp,
            "--record-replays", rec_dir]
    env = dict(os.environ)
    if strategy not in ("speedE", "speedtm"):
        env["HM_XLOG"] = "1"          # 实验候选自动开分歧探针（执行验证）
    with open(logp, "a", encoding="utf-8") as logf:
        p = subprocess.Popen(argv, cwd=ROOT, stdout=logf,
                             stderr=subprocess.STDOUT, env=env)
        code = p.wait()
    return room, logp, code


def wait_seconds_for(sec_now, target):
    """为"等到墙上时钟的秒 ≥ target"需要睡多少秒（已在窗口内 ⇒ 0）。

    ★ 2026-09-16 新增：为"入席秒 ↔ 同桌强度"的预登记实验（STATUS §9.87）提供机制。
    口径：target=50 时，秒 50~59 入席；秒 <50 则等到 50。
    """
    try:
        s, t = int(sec_now), int(target)
    except Exception:
        return 0
    if s >= t:
        return 0
    return t - s


def wait_until_second(target):
    """按需睡眠到秒 ≥ target；返回实际睡了多久（秒）。"""
    sec = time.localtime().tm_sec
    d = wait_seconds_for(sec, target)
    if d > 0:
        print("%s 等待入席窗口（当前 %d 秒 < 目标 %d 秒）⇒ 睡 %ds"
              % (ts(), sec, int(target), d), flush=True)
        time.sleep(d)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=6)
    ap.add_argument("--strategy", default="speedtm")
    ap.add_argument("--wait-until-second", type=int, default=None,
                    help="入席前等到墙上时钟的秒 ≥ N（预登记实验用；见 STATUS §9.87）")
    args = ap.parse_args()
    if not os.path.exists(TOKEN_FILE):
        raise SystemExit("缺 var/.global_token")
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    done = 0
    while done < args.rooms:
        print("%s 第 %d 房：/api/match 预占…" % (ts(), done + 1), flush=True)
        if args.wait_until_second is not None:
            wait_until_second(args.wait_until_second)
        # ★ 2026-09-17 修：`stamp` 必须取在**等待之后**。
        #   原实现把 stamp 放在 wait 之前 ⇒ 房目录/日志名记的是"准备入席"的时刻（如 23:33:29），
        #   而真正入席是等待结束后的 /api/match（如 23:33:50）⇒ 所有以"目录名的秒"为口径的分析
        #   （尤其 `var/_pool_signal_test.py` 的操纵检查）会把 B 臂读成"根本没等到 ≥50"，实验被误判。
        stamp = time.strftime("%Y%m%d_%H%M%S")
        try:
            room = api_match()
        except SystemExit:
            raise                       # 403 FEATURE_DISABLED：永久条件，直接退出
        except Exception as e:
            print("%s match 失败(%s)，30s 后重试" % (ts(), e), flush=True)
            time.sleep(30)
            continue
        print("%s 入房 %s（strategy=%s），开打…" % (ts(), room, args.strategy),
              flush=True)
        room2, logp, code = one_room(args.strategy, stamp)
        print("%s 房进程结束 code=%d，抓 ranking…" % (ts(), code), flush=True)
        archived = False
        for attempt in range(5):
            res = fetch_ranking(room)
            if res is not None:
                ranking, status = res
                rec = {"ts": ts(), "room": room, "strategy": args.strategy,
                       "status": status, "ranking": ranking,
                       "exit_code": code}
                with open(OUT_JSONL, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print("%s ranking 归档 %d 条" % (ts(), len(ranking)),
                      flush=True)
                archived = True
                break
            time.sleep(2)
        if not archived:
            print("%s 房 %s ranking 抓取失败（窗口已过）" % (ts(), room),
                  flush=True)
        done += 1
        if done < args.rooms:
            time.sleep(3)
    print("%s 完成 %d 房，退出" % (ts(), done))


if __name__ == "__main__":
    sys.exit(main())
