"""tools/fetch_replays —— 真机对局回放拉取器（蓝图 M2「事件流回拉器」）。

用途：
- 测试房间任一局结束后免认证拉完整事件流（四家手牌/逐事件摸打吃碰杠/局结果），
  落盘 JSON 供 复盘、算法优化、训练数据、本地引擎 vs 服务器口径校准；
- 与 本地 sim 输出对比可校准 模拟器语义（杠上花/连庄/副露窗口等未对齐项）。

用法：
    python tools/fetch_replays.py --room <房间id> [--out var/replays]
    python tools/fetch_replays.py --game <game_id>            # portal owner 登录态暂不支持
输出：var/replays/room_<id>/games.json + 每局 room_<id>_<batch>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.api import ApiError, Client          # noqa: E402
from bot.util import log, server_from_env      # noqa: E402


def fetch_room(client, room_id, out_dir, limit=0):
    """拉房间局列表 → 逐局事件流落盘。返回 (局数, 文件列表)。"""
    os.makedirs(out_dir, exist_ok=True)
    games = client.get("/api/test-rooms/%s/games" % room_id)
    if not isinstance(games, list):
        raise SystemExit("局列表格式异常: %r" % (games,)[:200])
    if limit:
        games = games[-limit:]
    saved = []
    for g in games:
        batch = g.get("batch")
        gid = g.get("game_id")
        if gid is None:
            log("跳过无 game_id 条目: %r", g)
            continue
        try:
            ev = client.get("/api/test-rooms/%s/games/%s/events" % (room_id, batch))
        except ApiError as e:
            if e.status == 403:
                log("局 %s 仍在进行（403 GAME_NOT_FINISHED），跳过", gid)
                continue
            raise
        path = os.path.join(out_dir, "room_%s_b%d_%s.json" % (room_id, batch, gid))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"meta": {"room": room_id, "batch": batch, "game": gid},
                       "events": ev}, f, ensure_ascii=False, indent=1)
        saved.append(path)
        log("已保存 %s（%d 事件）", path, len(ev) if isinstance(ev, list) else "?")
        time.sleep(0.25)                     # 每房间 5/s 限速
    # 汇总
    with open(os.path.join(out_dir, "games.json"), "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=1)
    log("完成：%d 局 → %s", len(saved), out_dir)
    return len(saved), saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="", help="测试房间 id")
    ap.add_argument("--game", default="", help="单局 game_id（需要 portal owner 登录态，暂未支持）")
    ap.add_argument("--out", default=os.path.join("var", "replays"))
    ap.add_argument("--limit", type=int, default=0, help="只拉最近 N 局（0=全部）")
    ap.add_argument("--server", default=server_from_env())
    args = ap.parse_args()
    if args.game:
        raise SystemExit("--game 依赖 portal owner 登录态（caddy 会话），当前工具仅支持 --room 免认证路径")
    if not args.room:
        ap.error("需要 --room <测试房间id>")
    out_dir = os.path.join(args.out, "room_%s" % args.room)
    try:
        fetch_room(Client(args.server), args.room, out_dir, args.limit)
    except ApiError as e:
        log("拉取失败: HTTP %s %s（房间不存在或已删除？）", e.status, e.code or e.body[:120])
        sys.exit(1)


if __name__ == "__main__":
    main()
