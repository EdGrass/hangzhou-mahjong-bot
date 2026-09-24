# -*- coding: utf-8 -*-
"""turn8_tenpai —— 逐臂的**第 8 巡听牌率**（⚠ **当前不成立，见下**）。

⚠ 2026-09-17 实测否掉：本地 `dec.jsonl` 的**弃牌记录不完整**（一个对局平均只有 ~68 条弃牌），
弃牌序号**不能**当巡次 ⇒ 本工具**不要**用作判据；第 8 巡听牌率请用门户复盘（`real_game_audit --min-rounds 8`）。

为什么需要：c151 的机制（压多对子）已在 §4c-73 确认生效，但**那只是手段**；
真正的目标指标是"**更快到听牌**"（依据 §4c-62：我们与同池强玩家的差距就是第 8 巡听牌率 +9.5pp）。

口径：
  - 数据 = 本地 `var/replays/auto_*/*.dec.jsonl`（每条是**我方自己的**一个决策）；
  - 巡次重建：按 `g`（对局 id）分组，`a.action=="discard"` 的**出现序号**就是我们的第 n 巡；
  - 取**第 8 次弃牌**时的手牌 `h`，用 `exact_shanten` 判定是否听牌 ⇒ 得到"第 8 巡听牌率"；
  - 臂归属：`var/_ab_log.jsonl` 的排批时刻。

用法：python -X utf8 tools/turn8_tenpai.py [--turn 8] [--since "..."]
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402


def arm_launches():
    out = []
    for ln in io.open(os.path.join(ROOT, "var", "_ab_log.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("arm") and d.get("ts"):
            out.append((d["ts"], str(d["arm"])))
    out.sort()
    return out


def dir_ts(name):
    try:
        return "%s-%s-%s %s:%s:%s" % (name[5:9], name[9:11], name[11:13],
                                      name[14:16], name[16:18], name[18:20])
    except Exception:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--turn", type=int, default=8)
    ap.add_argument("--since", default="")
    a = ap.parse_args(argv)
    since = a.since
    if not since:
        try:
            since = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8").read()).get("started") or ""
        except Exception:
            since = ""
    launches = arm_launches()
    # (arm) -> [n_seen, n_tenpai, mean_shanten]; 按 (game_id) 重建巡次
    per = collections.defaultdict(lambda: [0, 0, 0.0])
    for d in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*"))):
        name = os.path.basename(d)
        ts = dir_ts(name)
        if since and ts and ts < since:
            continue
        arm = None
        for lts, larm in launches:
            if lts <= ts:
                arm = larm
        if not arm:
            continue
        # game_id -> discard count
        cnt = collections.Counter()
        got = set()
        for f in sorted(glob.glob(os.path.join(d, "*.dec.jsonl"))):
            try:
                for ln in io.open(f, encoding="utf-8"):
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    if (r.get("a") or {}).get("action") != "discard":
                        continue
                    g = r.get("g") or ""
                    cnt[g] += 1
                    if cnt[g] != a.turn or (g, a.turn) in got:
                        continue
                    got.add((g, a.turn))
                    h = [str(x) for x in (r.get("h") or [])]
                    if len(h) < 2:
                        continue
                    try:
                        v = exact_shanten(h, qidui=True, exposed_melds=0, gangs=0)
                    except Exception:
                        continue
                    cell = per[arm]
                    cell[0] += 1
                    cell[1] += 1 if v == 0 else 0
                    cell[2] += v
            except Exception:
                pass
    if not per:
        print("（没有数据；等本轮战役出房）")
        return
    print("=" * 70)
    print("我方第 %d 巡**听牌率**（本地决策流，逐臂；窗口 since=%s）" % (a.turn, since or "-"))
    print("-" * 70)
    print("%-14s %6s %10s %12s" % ("arm", "n", "听牌率", "平均向听"))
    for arm in sorted(per):
        n, tp, sh = per[arm]
        if not n:
            continue
        print("%-14s %6d %9.1f%% %12.3f" % (arm, n, 100.0 * tp / n, sh / n))
    print("=" * 70)


if __name__ == "__main__":
    main()
