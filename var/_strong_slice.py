# -*- coding: utf-8 -*-
"""`var/_strong_slice.py` —— 把**强手房**的复盘切成一个语料目录，好让现成工具做分层读数。

## 为什么要有它

§V.156 已用四测真数据定案：**混场能打、强场打不动**（第 1 轮 +1.931 分/轮，第 2 轮 −1.038 分/轮）。
而 `var/_gate2.py` 的主/副端点把"强手房/弱房"**混在一起**（`var/_verdict_by_elite.py` 的
docstring 已写明这一点）⇒ 一个臂完全可能"只是在弱房更赚"。

选臂破平链（§V.66/§V.67）第 ② 步是**两半 Pareto**（A=听牌率/兑现率、B=番/爆头/赢分），
但这两条命令（`hu_gap_split`、`_seat_h2h`）目前都**只有全房口径** ⇒ 破平时看不出"弱房驱动"。
本工具补的就是这一步：按 `--since` 的台账房间 + 门户 topN，切出"**房里有 topN 对手**"的复盘文件，
再交给现成工具（不重写任何统计）：

    python -X utf8 var/_strong_slice.py --since "2026-09-23 03:13:44"
    # 它打印两条命令，例如：
    python -X utf8 tools/hu_gap_split.py --dirs <slice>/*.json --by-arm     # 按臂 × 强手房
    python -X utf8 tools/hu_gap_split.py --dirs <slice>/*.json              # 我方 / topN / 其他

## 只做什么

只读台账 + 复盘 + 门户榜；**只新增一个切片目录**（`var/replays/strong_<slug>/`，硬链接）。
不改任何臂、不动任何进程、不写任何判词。榜单不可达 ⇒ **直接失败**（绝不用空榜切出"假强手房"）。

用法：
    python -X utf8 var/_strong_slice.py --since "2026-09-23 03:13:44" [--topn 32] [--out strong_x]
"""
from __future__ import annotations
import argparse
import glob
import io
import json
import os
import re
import ssl
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECENT = os.path.join(ROOT, "var", "replays", "recent")
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
COOKIE = os.path.join(ROOT, "var", ".portal_cookie")
ME = "u_7a3fba48d70b"
ROOM_RX = re.compile(r"^(a_[0-9a-f]+)_")


def board_top(n=32):
    """门户全榜前 N 的 user_id 集合；拿不到就抛（绝不返回空集）。"""
    with io.open(COOKIE, encoding="utf-8-sig") as f:
        ck = f.read().strip()
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        "https://10.240.169.190:18080/portal/api/leaderboard?period=all",
        headers={"Cookie": ck})
    j = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode("utf-8"))
    tops = {r["user_id"] for r in (j.get("top") or [])[:n]}
    if not tops:
        raise RuntimeError("榜单返回空 ⇒ 拒绝切片（否则会切出'假强手房'）")
    return tops


def ledger_rooms(since):
    """since 之后开打的房间 id（台账 `room` 字段）。"""
    rooms = set()
    with io.open(LEDGER, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if (d.get("ts") or "") < since:
                continue
            r = d.get("room")
            if r:
                rooms.add(r)
    return rooms


def room_of(path):
    m = ROOM_RX.match(os.path.basename(path))
    return m.group(1) if m else None


def classify(path, tops):
    """读一份复盘 ⇒ (有我们?, 房里**别的** topN 对手有几个)。

    返回**个数**而不是 bool：预登记 §8 要求"≥2 名 top32"层（决赛相似层），
    调用方用 `--min-elite` 选层。
    """
    try:
        with io.open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None
    uids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
    if ME not in uids:
        return None
    return True, sum(1 for u in uids if u and u != ME and u in tops)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    # ★ R1459：本工具会读**上百份复盘**（且 `_strong_veto` 在判词那一刻会被 `_adopt_pair` **自动调用**）
    #   ⇒ 不降优先级就会与正在打的对局抢 CPU（R1182：会抬高提交延迟、丢动作）。开跑前自我降到 BelowNormal。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _lowprio_run import lower_self
        print("[strong_slice] %s" % lower_self())
    except Exception as _e:
        print("[strong_slice] 降级失败（继续跑）：%s" % str(_e)[:60])
    ap.add_argument("--topn", type=int, default=32)
    ap.add_argument("--out", default="", help="切片目录名（默认 strong_<slug>）")
    ap.add_argument("--min-elite", type=int, default=1,
                    help="房里至少有几个 topN 对手才算（默认 1；预登记 §8 的决赛相似层用 2）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不建目录")
    a = ap.parse_args(argv)

    try:
        tops = board_top(a.topn)
    except Exception as e:
        print("❌ 榜单不可达（%s）⇒ 不做切片" % str(e)[:80])
        return 2
    rooms = ledger_rooms(a.since)
    print("窗口台账房间：%d 个（since=%s）" % (len(rooms), a.since))
    if not rooms:
        print("❌ 该窗口台账里没有房间 ⇒ 检查 --since")
        return 2

    slug = a.out or ("strong%s_" % (a.min_elite if a.min_elite > 1 else "")
                     + re.sub(r"[^0-9]", "", a.since)[:12])
    outdir = os.path.join(ROOT, "var", "replays", slug)
    n_strong = n_weak = n_skip = n_other = 0
    strong_rooms, weak_rooms = set(), set()
    if not a.dry_run:
        os.makedirs(outdir, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(RECENT, "*.json"))):
        r = room_of(p)
        if not r or r not in rooms:
            n_other += 1
            continue
        c = classify(p, tops)
        if c is None:
            n_skip += 1
            continue
        if c[1] >= a.min_elite:
            n_strong += 1
            strong_rooms.add(r)
            if not a.dry_run:
                dst = os.path.join(outdir, os.path.basename(p))
                if not os.path.exists(dst):
                    try:
                        os.link(p, dst)          # 硬链接（同盘，零拷贝）
                    except Exception:
                        import shutil
                        shutil.copy2(p, dst)
        else:
            n_weak += 1
            weak_rooms.add(r)
    print("强手房（房里有 >=%d 个 top%d）：%d 间 / %d 份复盘 ｜ 其余：%d 间 / %d 份 ｜ 窗口外 %d 份 ｜ 读不了 %d 份"
          % (a.min_elite, a.topn, len(strong_rooms), n_strong, len(weak_rooms), n_weak, n_other, n_skip))
    if a.dry_run:
        print("（--dry-run：未建目录）")
        return 0
    print()
    print("按臂 × 强手房（听牌率/兑现率/爆头态率 等）：")
    print("  python -X utf8 tools/hu_gap_split.py --dirs %s/*.json --by-arm" % slug)
    print("强手房里的 我方 / top%d / 其他：" % a.topn)
    print("  python -X utf8 tools/hu_gap_split.py --dirs %s/*.json" % slug)
    print("分/房 + 第1率 分层（台账口径，与本切片互补）：")
    print('  python -X utf8 var/_verdict_by_elite.py --since "%s" --arms <A>,<B>' % a.since)
    print()
    print("切片目录：%s" % os.path.relpath(outdir, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
