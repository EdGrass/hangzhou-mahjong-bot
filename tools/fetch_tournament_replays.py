"""fetch_tournament_replays.py —— 按**锦标赛 id** 补拉官方复盘（门户格式）。

为什么需要（§9.40）：赛后审计 `real_game_audit --dirs official_1024_<stamp>` 读不了本地录制格式
（`<gid>.jsonl` 裸事件流）⇒ 必须先从门户拉**门户格式**（含 `seats`/`blocks`）的复盘。
`tools/replay_fetch.py` 实测不可用；`fetch_room_replays.py` 只认自动房。本工具补上这块。

流程：
  1) `GET /api/tournaments/{tid}`（**Bearer** 认证）→ `my_games` / `my_games_by_batch`
  2) 从每个 game 里取 `game_id`（或 `gid`/`id`）；若只有 `room_id`，再走
     `GET /portal/api/test-rooms/{room}`（**实证路径**）→ `games[].game_id`
  3) `GET /portal/api/games/{gid}/events` → 落到 `<out>/<gid>.json`
  4) 打印可直接粘贴的 `real_game_audit` 命令

⚠ **认证（实证）**：`/api/*` 用 `Authorization: Bearer <token>`；`/portal/api/*` 用 `Cookie: <var/.portal_cookie>`。
⚠ **验证状态**：① `GET /api/tournaments/{tid}`（Bearer）**已实测 200**，`my_games` 结构确认（开赛前为空）；
② 拉取那半段（`/portal/api/games/{gid}/events`）**用自动房验证过路径与认证**，
   但**锦标赛房的 room→gid 路径尚未在真数据上跑过**（比赛未开始）⇒ **赛后第一次跑要留意输出**。

用法：
  python -X utf8 tools/fetch_tournament_replays.py                      # 用 var/.token_1024_20260917 + 二测 tid
  python -X utf8 tools/fetch_tournament_replays.py --tid t_xxx --token-file var/.token_xxx
  python -X utf8 tools/fetch_tournament_replays.py --out var/replays/official_probe --dry-run
"""
from __future__ import annotations
import argparse, io, json, os, ssl, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("HM_SERVER", "").strip() or "http://127.0.0.1:8080"
CTX = ssl._create_unverified_context()


def get(path, token, cookie="", tries=3):
    """⚠ 认证分两套（实证）：`/api/*` 用 **Bearer**；`/portal/api/*` 用 **Cookie**。"""
    for i in range(tries):
        hdr = ({"Cookie": cookie} if (path.startswith("/portal/api") and cookie)
               else {"Authorization": "Bearer " + token})
        req = urllib.request.Request(BASE + path, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.status == 429:
                time.sleep(min(30, 4 * (2 ** i)))
                continue
            return e.code, ""
        except Exception:
            time.sleep(2 * (i + 1))
    return 0, ""


def game_ids_from_detail(detail):
    out = []
    def take(obj):
        if isinstance(obj, dict):
            for k in ("game_id", "gid", "id"):
                v = obj.get(k)
                if isinstance(v, str) and v and v not in out:
                    out.append(v)
    for g in (detail.get("my_games") or []):
        take(g)
    mb = detail.get("my_games_by_batch") or {}
    if isinstance(mb, dict):
        for v in mb.values():
            if isinstance(v, list):
                for g in v:
                    take(g)
            else:
                take(v)
    return out


def room_ids_from_detail(detail):
    out = []
    def take(obj):
        if isinstance(obj, dict):
            for k in ("room_id", "room", "game_room"):
                v = obj.get(k)
                if isinstance(v, str) and v and v not in out:
                    out.append(v)
    for g in (detail.get("my_games") or []):
        take(g)
    mb = detail.get("my_games_by_batch") or {}
    if isinstance(mb, dict):
        for v in mb.values():
            if isinstance(v, list):
                for g in v:
                    take(g)
            else:
                take(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", default="")
    ap.add_argument("--token-file", default=os.path.join(ROOT, "var", ".token_1024_20260917"))
    ap.add_argument("--out", default=os.path.join(ROOT, "var", "replays", "official_fetched"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="最多拉几个 gid（0=全部；调试用）")
    a = ap.parse_args()

    token = io.open(a.token_file, encoding="utf-8-sig").read().strip()
    if not token:
        raise SystemExit("empty token file: %s" % a.token_file)
    ck_path = os.path.join(ROOT, "var", ".portal_cookie")
    cookie = io.open(ck_path, encoding="utf-8-sig").read().strip() if os.path.exists(ck_path) else ""

    st, body = get("/api/tournaments/%s" % a.tid, token)
    print("GET /api/tournaments/%s -> %s" % (a.tid, st))
    if st != 200:
        # ⚠ 老赛事/非参赛者查详情会 403/404 —— **不致命**：下面用 /portal/api/test-rooms/{tid} 兜底
        print("  ⚠ 详情拉取失败（%s）⇒ 改用 /portal/api/test-rooms/{tid} 兜底列 games" % st)
        detail = {}
    else:
        detail = json.loads(body)
    print("  status=%s  my_games=%d  registered=%s  ready=%s" % (
        detail.get("status"), len(detail.get("my_games") or []),
        detail.get("registered_users"), detail.get("ready_users")))

    gids = game_ids_from_detail(detail)
    rooms = room_ids_from_detail(detail)
    print("  从锦标赛详情取到 gid=%d 个、room=%d 个" % (len(gids), len(rooms)))

    # ★ 兜底（实证）：/portal/api/test-rooms/{room} 对**自动房与锦标赛房都可用**；
    #   即便 /api/tournaments/{tid} 拿不到（老赛事 404），也能从 tid 直接列 games。
    rooms = rooms or [a.tid]
    for room in rooms:
        st2, b2 = get("/portal/api/test-rooms/%s" % room, token, cookie)
        if st2 == 200 and b2:
            try:
                for g in (json.loads(b2).get("games") or []):
                    gid = g.get("game_id")
                    if gid and g.get("status") == "finished" and gid not in gids:
                        gids.append(gid)
            except Exception:
                pass
        time.sleep(0.5)

    if a.limit:
        gids = gids[:a.limit]
    if not gids:
        print("⚠ 没有拿到任何 gid（可能比赛尚未开始/尚未落库）。届时重跑本脚本即可。")
        return 0

    os.makedirs(a.out, exist_ok=True)
    ok = skip = fail = 0
    for gid in gids:
        dst = os.path.join(a.out, "%s.json" % gid)
        if os.path.exists(dst):
            skip += 1
            continue
        if a.dry_run:
            print("  [dry-run] 将拉 /portal/api/games/%s/events → %s" % (gid, dst))
            continue
        st3, b3 = get("/portal/api/games/%s/events" % gid, token, cookie)
        if st3 == 200 and b3 and '"blocks"' in b3:
            io.open(dst, "w", encoding="utf-8").write(b3)
            ok += 1
        else:
            print("  gid %s 失败 %s" % (gid, st3))
            fail += 1
        time.sleep(0.8)

    print("完成：新增 %d，已存在 %d，失败 %d；目录 %s" % (ok, skip, fail, a.out))
    rel = os.path.basename(os.path.normpath(a.out))
    print("接下来：")
    print("  python -X utf8 tools/real_game_audit.py --dirs %s --top 8 --min-rounds 8" % rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
