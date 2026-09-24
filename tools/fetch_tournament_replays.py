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
BASE = "https://10.240.169.190:18080"
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
        # ★ R1395：四测真数据首跑才发现：`my_games` 是**字符串 gid 列表**
        #   （实测 `['t_6266386bfd56_b1_t17', ...]`），而旧代码只处理 dict 元素
        #   ⇒ “从锦标赛详情取到 gid=0 个”，复盘**一张都拉不到**。这里把字符串当 gid 直接收下。
        if isinstance(obj, str):
            if obj and obj not in out:
                out.append(obj)
            return
        if isinstance(obj, dict):
            for k in ("game_id", "gid", "id"):
                v = obj.get(k)
                if isinstance(v, str) and v and v not in out:
                    out.append(v)
    for g in (detail.get("my_games") or []):
        take(g)
    mb = detail.get("my_games_by_batch") or {}
    # ★ R1396：四测实测 —— `my_games_by_batch` 含**同批次别人的对局**（拉它们全部 403 not a participant），
    #   而 `my_games`（字符串 gid，实测 10 条）才是**我们真正参与的对局**。
    #   故只有 `my_games` 一条 gid 都拿不到时才回退到 batch 字段（保留向后兼容，不再制造 403/拉高 429 风险）。
    if not out and isinstance(mb, dict):
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
    # ★ R1337：原默认是**09-17 二测**（tid + 令牌文件）⇒ 裸跑会去拉已结束的赛事。
    #   现在：缺省从 `.official_spec.json` 取，再回退到门户当前唯一 registering 赛事；取不到就报错退出 2。
    ap.add_argument("--tid", default="")
    ap.add_argument("--token-file", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "var", "replays", "official_fetched"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="最多拉几个 gid（0=全部；调试用）")
    a = ap.parse_args()

    _sp = {}
    try:
        _sp = json.loads(io.open(os.path.join(ROOT, "var", ".official_spec.json"), encoding="utf-8-sig").read())
    except Exception:
        _sp = {}
    _tid_src = ""
    if not a.tid:
        a.tid = str(_sp.get("tournament_id") or "")
        if a.tid:
            _tid_src = "spec"
    if not a.tid:
        try:
            _ck = io.open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
            _st, _body = get("/portal/api/tournaments", "", cookie=_ck)
            _ts = json.loads(_body) if _body else []
            _ts = _ts if isinstance(_ts, list) else (_ts.get("tournaments") or [])
            _reg = [t for t in _ts if str(t.get("status")) == "registering" and t.get("id")]
            if len(_reg) == 1:
                a.tid = str(_reg[0]["id"])
                _tid_src = "portal"
                print("从门户取到唯一 registering 赛事：%s" % (a.tid,))
        except Exception as _e:
            print("⚠ 门户查询失败：%s" % str(_e)[:100])
    if not a.tid:
        print("❌ 无法确定 --tid（spec 无 tournament_id、门户也没有唯一 registering 赛事）（拒绝沿用历史默认值 t_65d538e905c5）")
        return 2
    if not a.token_file:
        # ★ R1337：**tid 与令牌必须同源**（同 R1315）：tid 来自门户时不能拿 spec 里可能属于别场的令牌。
        if _tid_src == "spec":
            a.token_file = str(_sp.get("token_file") or "")
        if not a.token_file:
            a.token_file = os.path.join(ROOT, "var", ".global_token")
            if _tid_src == "portal":
                print("⚠ tid 来自门户（registering）；令牌回退到 var/.global_token（spec 里的令牌属于别场，已忽略）")
        if not os.path.isabs(a.token_file):
            a.token_file = os.path.join(ROOT, a.token_file)
    print("代为拉取：tid=%s  token=%s  out=%s" % (a.tid, os.path.relpath(a.token_file, ROOT), a.out))
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
