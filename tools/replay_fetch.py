"""tools/replay_fetch —— 窗口/房复盘拉取（server API 探索式）。

按候选端点顺序尝试拉取并校验返回含 'blocks' 的 JSON；成功即按
<tournament>_b<board>_t<table>.json 落盘 var/replays/<tid>/。
端点清单来自既有复盘文件命名与门户指南；拉取失败会给出提示（此时可用
run_bot --record-replays 的本地事件流兜底）。

用法：python tools/replay_fetch.py <tournament_id> [--cookie majiang_sid=...]
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()
CANDIDATES = [
    "/api/replays/{tid}",
    "/api/tournaments/{tid}/replays",
    "/portal/api/replays/{tid}",
]


def fetch(tid, cookie):
    h = {"Cookie": cookie} if cookie else {}
    for path in CANDIDATES:
        url = BASE + path.format(tid=tid)
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, dict) and "blocks" in data:
                return data
            if isinstance(data, list) and data and "blocks" in data[0]:
                return data
        except (urllib.error.HTTPError, urllib.error.URLError,
                json.JSONDecodeError, TimeoutError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tid")
    ap.add_argument("--cookie", default="")
    ap.add_argument("--out", default=os.path.join("var", "replays"))
    args = ap.parse_args()
    cookie = args.cookie or (open(os.path.join("var", ".portal_cookie"),
                                  encoding="utf-8-sig").read().strip()
                             if os.path.exists(os.path.join("var",
                                                            ".portal_cookie"))
                             else "")
    d = fetch(args.tid, cookie)
    if d is None:
        print("拉取失败：端点均未命中（用 run_bot --record-replays 兜底）")
        return 1
    out = os.path.join(args.out, args.tid)
    os.makedirs(out, exist_ok=True)
    if isinstance(d, dict):
        blocks = d.get("blocks", [])
        with open(os.path.join(out, args.tid + "_full.json"), "w",
                  encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        print("已落盘 blocks=%d → %s" % (len(blocks), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
