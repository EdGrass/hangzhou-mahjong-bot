"""tools/room_ctl —— 测试房全自助控制（门户 cookie）。

用法：
    python tools/room_ctl.py create [--m 10] [--rounds 16] [--name 自动对战]
    python tools/room_ctl.py close <room_id>
    python tools/room_ctl.py list
环境：HM_PORTAL_COOKIE=majiang_sid=... （未设则用 --cookie）
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()


def _cookie():
    c = os.environ.get("HM_PORTAL_COOKIE", "").strip()
    if not c:
        raise SystemExit("需要门户 cookie：set HM_PORTAL_COOKIE=majiang_sid=... 或 --cookie")
    return c


def _call(method, path, body=None, cookie=None):
    data = None
    h = {"Cookie": cookie or _cookie(), "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=15, context=CTX)
        return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))
        except Exception:
            msg = str(e)
        return e.code, msg


def create(m, rounds, name, cookie):
    body = {"M": m, "Rounds": rounds}
    if name:
        body["name"] = name
    code, d = _call("POST", "/portal/api/test-rooms", body, cookie)
    if code != 200:
        raise SystemExit("创建失败 %s: %s" % (code, d))
    print("房间 %s 已创建（M=%s, rounds=%s, status=%s）" %
          (d["room_id"], m, rounds, d.get("status")))
    for p in d.get("players", []):
        print("  %s=%s" % (p["name"], p["token"]))
    return d


def close(room_id, cookie):
    code, d = _call("POST", "/portal/api/test-rooms/%s/close" % room_id,
                    cookie=cookie)
    print("%s → %s" % (room_id, d if isinstance(d, dict) else d))
    return code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("create", "close", "list"))
    ap.add_argument("room", nargs="?", default="")
    ap.add_argument("--m", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=16)
    ap.add_argument("--name", default="")
    ap.add_argument("--cookie", default="")
    args = ap.parse_args()
    cookie = args.cookie or _cookie()
    if args.cmd == "create":
        create(args.m, args.rounds, args.name, cookie)
    elif args.cmd == "close":
        if not args.room:
            ap.error("close 需要 room_id")
        close(args.room, cookie)
    else:
        code, d = _call("GET", "/portal/api/test-rooms", cookie=cookie)
        print(code, json.dumps(d, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
