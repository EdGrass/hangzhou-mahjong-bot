# -*- coding: utf-8 -*-
"""批量拉取自动房全信息复盘 → `var/replays/recent/<gid>.json`。

每房 `/portal/api/test-rooms/{room}` → games[] → 每 gid `/portal/api/games/{gid}/events`
→ 落盘（含四家手牌，供 `tools/ab_winrate.py` / `mech_mix.py` / `real_game_audit.py` 用）。

**为什么要它**：本地 `run_bot --record-replays` 写的是**我方事件流**（`*.dec.jsonl`），
而按局胜率/番型/机制核对需要**服务器权威的四家全信息复盘**；门户复盘有发布延迟，
所以 A/B 期间要**周期性补拉**，否则 `ab_winrate.py` 会一直读到旧窗口（实测本地 `server` 目录停在 09-14）。

**限速**：每请求间隔 `--gap`（默认 1.2s），429 指数退避；**默认只拉最近 `--rooms`（8）房**
（一房约 80 个请求 ⇒ 8 房 ≈ 10 分钟）。**不要**在无人看着的时候跑全量。

用法：
    python -X utf8 tools/fetch_room_replays.py                 # 最近 8 房
    python -X utf8 tools/fetch_room_replays.py --rooms 20 --gap 1.5
    python -X utf8 tools/fetch_room_replays.py --since "2026-09-16 00:48:02"
    python -X utf8 tools/fetch_room_replays.py --dry-run       # 只列出会拉的房
"""
from __future__ import annotations
import argparse, glob, io, json, os, ssl, sys, time
import urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()
OUT = os.path.join(ROOT, "var", "replays", "recent")


def _cookie():
    p = os.path.join(ROOT, "var", ".portal_cookie")
    return io.open(p, encoding="utf-8-sig").read().strip()


class Fetcher:
    def __init__(self, cookie, gap=1.2, tries=4):
        self.cookie, self.gap, self.tries = cookie, gap, tries

    def get(self, path):
        for i in range(self.tries):
            req = urllib.request.Request(BASE + path, headers={"Cookie": self.cookie})
            try:
                with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.status == 429:
                    time.sleep(min(60, 6 * (2 ** i)))
                    continue
                return e.code, ""
            except Exception:
                time.sleep(3 * (i + 1))
        return 429, ""


def rooms_to_fetch(rooms, out_dir, limit, since=None):
    """纯函数：给定 [(room, strategy, ts)]，返回还没拉到的 (room, strategy, ts) 列表（尾部 N 个）。"""
    have = set()
    for p in glob.glob(os.path.join(out_dir, "*.json")):
        have.add(os.path.basename(p))
    out = []
    for room, strat, ts in rooms:
        if not room:
            continue
        if since and ts and ts < since:
            continue
        out.append((room, strat, ts))
    return out[-limit:] if limit else out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=8, help="只拉最近的 N 房（0=全部，慎用）")
    ap.add_argument("--gap", type=float, default=1.2, help="每个请求的最小间隔秒")
    ap.add_argument("--since", default="", help="只拉该时间戳之后的房")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    rp = os.path.join(ROOT, "var", "auto_ranking.jsonl")
    rows = []
    for ln in io.open(rp, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        rows.append((d.get("room") or "", d.get("strategy") or "?", d.get("ts") or ""))
    os.makedirs(OUT, exist_ok=True)
    todo = rooms_to_fetch(rows, OUT, a.rooms, since=(a.since or None))
    print("候选 %d 房（最近 %s）⇒ 本次处理 %d 房" % (len(rows), a.rooms or "全部", len(todo)))
    for room, strat, ts in todo:
        print("  %s  %-14s %s" % (room, strat, ts))
    if a.dry_run:
        print("--dry-run：未发请求")
        return

    f = Fetcher(_cookie(), gap=a.gap)
    ok = fail = skip = 0
    for room, strat, ts in todo:
        st, body = f.get("/portal/api/test-rooms/%s" % room)
        time.sleep(a.gap)
        if st != 200:
            print("room %s 列表失败 %s" % (room, st))
            fail += 1
            continue
        try:
            d = json.loads(body)
        except Exception:
            print("room %s 返回不是 JSON" % room)
            fail += 1
            continue
        gids = [g.get("game_id") for g in (d.get("games") or [])
                if g.get("status") == "finished" and g.get("game_id")]
        n_new = 0
        for gid in gids:
            out = os.path.join(OUT, "%s.json" % gid)
            if os.path.exists(out):
                skip += 1
                continue
            st2, b2 = f.get("/portal/api/games/%s/events" % gid)
            time.sleep(a.gap)
            if st2 == 200 and b2:
                with io.open(out, "w", encoding="utf-8") as fh:
                    fh.write(b2)
                ok += 1
                n_new += 1
            else:
                print("  gid %s 失败 %s" % (gid, st2))
                fail += 1
        print("room %s（%s）: 已发布 %d 局，本次新增 %d" % (room, strat, len(gids), n_new))
    print("完成: 新增 %d，失败 %d，跳过已存在 %d" % (ok, fail, skip))


if __name__ == "__main__":
    main()
