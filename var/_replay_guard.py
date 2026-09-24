# -*- coding: utf-8 -*-
"""`var/_replay_guard.py` -- 战役复盘覆盖看护（**只新增、只读台账、只写复盘目录**）。

## 为什么需要（2026-09-24 R1170 的收尾动作）

R1170 把"我们 vs 前几名"的差距拆到了机制层（听牌率 −6.44pp、做庄局胡率 −6.5pp、
庄胡收 = 差距 66%）。但**这些机制读数来自 `var/replays/server`，而那套语料停在 2026-09-14** ——
真正的原因是**读尺工具默认只读 `server` 这个静态快照**，而不是持续在补的 `recent`
（`tools/hu_gap_split.py` 已在本轮加 `--dir recent`，对齐**当前**语料）。

同时发现 `recent` 的**新鲜度**缺口：役 2（since 2026-09-23 03:13:44）共 60 房 = **600 个 gid**
（1 房 = 10 gid × 8 轮 = 80 轮；⚠ 台账 `ranking[].games_played` 是**轮数**、不是 gid 数），
其中 **20:30 之后完结的最近 8 房覆盖为 0（520/600 = 86.7%）**；本看护补齐后 **600/600 = 100%**。

后果（不修就有）：役次判词只能给"净胜/房"主端点，**机制端点（听牌率/庄家分账）在当轮数据上算不准** ——
这正是 R1163 ⑤ 与 §V.7 反复撞到的同一堵墙（"工具测不了"）。

## 做什么

按台账 `var/auto_ranking.jsonl` 里的**已完结房**（默认 `--since` 起），**从新到旧**补齐
门户四家全信息复盘到 `var/replays/recent/<gid>.json`（gid = `<room>_r<r>_b<b>_t<t>`）：

- **零 HTTP 的快路径**：先数本地已有 `<room>_*` 文件；`>= 该房 games_played` ⇒ **直接跳过、不查门户**；
- 只对**缺口的 gid** 发请求（已存在的**绝不覆盖**）；
- 单次运行有**硬预算**（`--max-fetch` 个 gid / `--max-minutes` 分钟），到点就干净退出，
  下一次计划任务接着补 ⇒ **永不长跑**；
- 全部网络失败只记日志、**不抛异常**（看护不能反噬主链）；
- **无缺口 ⇒ 完全不写日志**（避免每 15 分钟刷屏）。

## 红线

不杀进程、不改 `bot/`、不碰在途 A/B（`match_super`/`run_bot` 与本脚本无任何文件交集：
它们写 `*.dec.jsonl`，本脚本只写 `var/replays/recent/<gid>.json`）；只发门户 GET。

用法：
    python -X utf8 var/_replay_guard.py --dry-run          # 只看会补多少
    python -X utf8 var/_replay_guard.py                    # 默认补最近缺口（≤120 gid / 6 分钟）
    python -X utf8 var/_replay_guard.py --since "2026-09-23 03:13:44" --max-fetch 400
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from fetch_room_replays import Fetcher, _cookie  # noqa: E402

LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
RECENT = os.path.join(ROOT, "var", "replays", "recent")
LOG = os.path.join(ROOT, "var", "_replay_guard.log")
DEFAULT_SINCE = "2026-09-23 03:13:44"      # 役 2 起点（仅作回退）
AB_MODE = os.path.join(ROOT, "var", ".ab_mode")


def default_since(ab_path=None):
    """默认只补**当前战役**的房：从 `var/.ab_mode` 取 `started`；读不到才回退历史常量。

    为什么（R1427）：旧实现把役 2 起点写成默认，而计划任务**不传参** ⇒
    下一役开始后看护会一直只补役 2 的旧房，**新役的复盘永远不补** ⇒ 判词因覆盖 <70% 而 REFUSE。
    """
    path = ab_path or AB_MODE
    try:
        import json as _json
        with io.open(path, encoding="utf-8-sig") as fh:
            st = (_json.load(fh) or {}).get("started")
        if st:
            return str(st)
    except Exception:
        pass
    return DEFAULT_SINCE
      # 役 2 起点；换役时用 --since 覆盖或改这里
ROUNDS_PER_GID = 8                        # 实证：recent 抽样 4000 个 gid **全部** 8 轮（R1171）


def _log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def load_rooms(path=None, since=None, only_finished=True):
    """读台账 ⇒ [(room, strategy, ts)]，**按时间倒序**（新的在前）。

    ⚠ `path` 默认值**必须在调用时解析**（不能写成 `path=LEDGER`）：
    模块级常量一旦被测试/调用方覆盖，`def` 期绑定的默认值会**指回真实台账** ——
    R1171 自查时这真的发生过（测试以为自己指向 tmp，实际在读线上台账）。
    """
    path = path or LEDGER
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        room = d.get("room")
        if not room:
            continue
        if only_finished and d.get("status") != "finished":
            continue
        ts = d.get("ts") or ""
        if since and ts and ts < since:
            continue
        out.append((room, d.get("strategy") or "?", ts))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


def expected_gids(rec, rounds_per_gid=ROUNDS_PER_GID):
    """一房应有多少个 gid。

    ⚠ **单位陷阱（R1171 实测纠正）**：台账 `ranking[].games_played` 是**轮数**，不是 gid 数。
    实证：归档的 **896 房**里 **895 房有 10 个 gid**、**全部** `games_played=80`，且
    `recent` 抽样 **4000 个 gid 全部 8 轮** ⇒ **1 房 = 10 gid × 8 轮 = 80 轮**。
    早先按"80 个 gid"算过覆盖率（10.8%），**分母错了 8 倍**，一并纠正。
    """
    vals = []
    for r in (rec.get("ranking") or []):
        try:
            vals.append(int(r.get("games_played") or 0))
        except Exception:
            pass
    g = max(vals) if vals else 0
    return (g + rounds_per_gid - 1) // rounds_per_gid if g else 0


def rooms_with_expect(dirpath, since=None, path=None):
    """[(room, strategy, ts, expected)]，新→旧。expected 来自台账 ranking。"""
    path = path or LEDGER
    exp = {}
    with io.open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("room"):
            exp[d["room"]] = expected_gids(d)
    return [(r, s, t, exp.get(r, 0)) for (r, s, t) in load_rooms(path, since)]


def have_gids(dirpath, room):
    """本地已归档该房的 gid 集合（按 `<room>_` 前缀精确匹配，不会把 a_ab 认成 a_abc）。"""
    pref = room + "_"
    out = set()
    for p in glob.glob(os.path.join(dirpath, "%s*.json" % room)):
        b = os.path.basename(p)[:-5]
        if b.startswith(pref):
            out.add(b)
    return out


def fetch_room(f, room, gids, dirpath, gap, budget_left, dry_run=False):
    """拉取 gids 中缺失的部分；返回 (新增数, 失败数, 询问数)。不覆盖已有文件。"""
    ok = fail = ask = 0
    for gid in gids:
        if budget_left[0] <= 0:
            break
        out = os.path.join(dirpath, "%s.json" % gid)
        if os.path.exists(out):
            continue
        budget_left[0] -= 1
        ask += 1
        if dry_run:
            continue
        st, body = f.get("/portal/api/games/%s/events" % gid)
        time.sleep(gap)
        if st == 200 and body:
            try:
                with io.open(out, "w", encoding="utf-8") as fh:
                    fh.write(body)
                ok += 1
            except Exception:
                fail += 1
        else:
            fail += 1
    return ok, fail, ask


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=default_since(), help="只补该时间之后的房（默认=当前战役 .ab_mode.started）")
    ap.add_argument("--max-fetch", type=int, default=120, help="单次运行最多请求多少个 gid")
    ap.add_argument("--max-minutes", type=float, default=6.0, help="单次运行墙钟上限（分钟）")
    ap.add_argument("--gap", type=float, default=1.2, help="每请求最小间隔秒")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ledger", default="", help="台账路径（默认 var/auto_ranking.jsonl）")
    ap.add_argument("--recent", default="", help="复盘输出目录（默认 var/replays/recent）")
    a = ap.parse_args(argv)

    ledger = a.ledger or LEDGER
    recent = a.recent or RECENT
    if not os.path.isdir(recent):
        os.makedirs(recent, exist_ok=True)
    t0 = time.time()
    deadline = t0 + a.max_minutes * 60

    rooms = rooms_with_expect(recent, a.since, path=ledger)
    todo = []
    for room, strat, ts, exp in rooms:
        have = have_gids(recent, room)
        if exp and len(have) >= exp:
            continue                                  # 快路径：已满 ⇒ 一次 HTTP 都不发
        todo.append((room, strat, ts, exp, len(have)))

    if not todo:
        return 0                                      # 无缺口 ⇒ 静默
    if not a.quiet:
        print("战役房 %d 个，其中未覆盖 %d 个（since=%s）" % (len(rooms), len(todo), a.since))
        for room, strat, ts, exp, got in todo[:10]:
            print("  %s  %-14s %s  %d/%d" % (room, strat, ts, got, exp))

    if a.dry_run:
        print("--dry-run：未发请求")
        return 0

    try:
        f = Fetcher(_cookie(), gap=a.gap)
    except Exception as e:
        _log("cookie 读取失败，跳过：%s" % e)
        return 0

    budget = [a.max_fetch]
    tot_ok = tot_fail = tot_ask = tot_rooms = 0
    for room, strat, ts, exp, got in todo:
        if budget[0] <= 0 or time.time() >= deadline:
            break
        st, body = f.get("/portal/api/test-rooms/%s" % room)
        time.sleep(a.gap)
        if st != 200:
            tot_fail += 1
            continue
        try:
            d = json.loads(body)
        except Exception:
            tot_fail += 1
            continue
        gids = [g.get("game_id") for g in (d.get("games") or [])
                if g.get("status") == "finished" and g.get("game_id")]
        ok, fail, ask = fetch_room(f, room, gids, recent, a.gap, budget)
        tot_ok += ok; tot_fail += fail; tot_ask += ask; tot_rooms += 1
        if not a.quiet:
            print("  %s（%s）: 已发布 %d，本次新增 %d" % (room, strat, len(gids), ok))
        if time.time() >= deadline:
            break

    if tot_ask or tot_fail:
        _log("补复盘: 房 %d / 请求 %d / 新增 %d / 失败 %d / 用时 %.1fs（since=%s）"
             % (tot_rooms, tot_ask, tot_ok, tot_fail, time.time() - t0, a.since))
    if not a.quiet:
        print("完成: 新增 %d，失败 %d，请求 %d，用时 %.1fs" % (tot_ok, tot_fail, tot_ask, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





