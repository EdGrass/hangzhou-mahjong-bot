# -*- coding: utf-8 -*-
"""`var/_pick_arm.py` —— **正式赛选臂（§V.66 口径）的"算术自动化"**（只读台账，毫秒级）。

## 为什么只做算术、不做裁决

§V.66 的规则是：① 主序列 = **强手房分/房**（房数 ≥30），但 **|Δ| < 2×SE 视为不可区分**（SE 用合并口径）；
② 不可区分时用 **两半 Pareto** 破平（半边 A = 听牌率/兑现率；半边 B = 番·爆头·赢分）；
③ 再平 ⇒ 第 1 率；④ 再平 ⇒ 最近一役判词；⑤ 都不理想 ⇒ 最近验证过的基线。

其中 **②必须人读两张表**（`hu_gap_split --by-arm` 与 `_seat_h2h --by-arm --top 32`）——
把它们硬解析成"自动推荐"反而是**T-6h 最危险的自动化**（解析错就会选错臂）。
所以本工具**只自动化最容易算错的算术**（SE / 2×SE 不可区分判定 / 排序 / 第1率），
并把"接下来该跑哪两条命令、按什么规则读"直接打出来。

用法：
    python -X utf8 var/_pick_arm.py --since "2026-09-20" --min-rooms 30
    python -X utf8 var/_pick_arm.py --since "2026-09-20" --strong-top 32
"""
from __future__ import annotations
import argparse, collections, glob, io, json, math, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"


def top32():
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from gang_gap import board_top
        return {u for _r, u, _n in board_top(32)}
    except Exception:
        return set()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--min-rooms", type=int, default=30)
    ap.add_argument("--strong-top", type=int, default=32)
    ap.add_argument("--me", default=ME)
    ap.add_argument("--allow-no-board", action="store_true",
                    help="榜单不可达时仍输出全部房口径表（仅供参考，不可用于选臂）")
    a = ap.parse_args(argv)
    top = top32()
    if not top:
        # ★ R1326：本工具的**主排序列就是“强手房分/房”**（§V.67）。
        #   榜单不可达时不能“退化成无分层”——那样每个臂的强手列都是 nan、
        #   排序变成随机，而读者很可能只看“前两名”那行就定案 —— 这正是§V.67 最担心的“无意义但看起来正常”。
        #   所以默认**失败**（宁可不给结论）；只有显式加 --allow-no-board 才输出“仅供参考、不可用于选臂”的表。
        if not a.allow_no_board:
            print("❌ 榜单不可达 ⇒ **本工具不给结论**（主排序列依赖强手分层）。")
            print("   先修榜单（门户 cookie / 网络）后重跑；应急看全部房粗表：加 --allow-no-board（**不可用于选臂**）")
            return 2
        print("⚠️ 榜单不可达，且已显式加 --allow-no-board ⇒ 下表为**全部房口径**，仅供参考，不可用于选臂")

    rows = []
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") != "finished" or (d.get("ts") or "") < a.since:
            continue
        rk = d.get("ranking") or []
        mine = [x for x in rk if x.get("user_id") == a.me]
        if not mine:
            continue
        uids = [x.get("user_id") for x in rk]
        strong = any(u in top for u in uids if u != a.me)
        rows.append((d.get("strategy") or "?", float(mine[0].get("total_score") or 0),
                     int(mine[0].get("rank") or 0), strong))

    by = collections.defaultdict(lambda: {"all": [], "strong": [], "first": 0})
    for arm, score, rank, strong in rows:
        c = by[arm]
        c["all"].append(score)
        if strong:
            c["strong"].append(score)
        if rank == 1:
            c["first"] += 1

    table = []
    for arm, c in by.items():
        n = len(c["all"])
        ns = len(c["strong"])
        if n < a.min_rooms:
            continue
        mean_s = statistics.mean(c["strong"]) if ns >= 5 else float("nan")
        sd_s = statistics.stdev(c["strong"]) if ns >= 2 else float("nan")
        se_s = sd_s / math.sqrt(ns) if ns >= 2 else float("nan")
        table.append({"arm": arm, "n": n, "ns": ns, "mean_strong": mean_s, "se": se_s,
                      "mean_all": statistics.mean(c["all"]), "first": c["first"] / n})
    if not table:
        print("没有满足 --min-rooms 的臂"); return 2

    table.sort(key=lambda r: (-r["mean_strong"] if not math.isnan(r["mean_strong"]) else -1e9))
    print("=" * 104)
    print("正式赛选臂（§V.66）：since=%s  仅列房数 ≥%d 的臂；按**强手房分/房**排序" % (a.since, a.min_rooms))
    print("=" * 104)
    print("%-24s %5s %6s %12s %9s %10s %8s" % ("臂", "房数", "强手房", "强手房分/房", "SE", "全部分/房", "第1率"))
    for r in table:
        print("%-24s %5d %6d %12.1f %9.1f %10.1f %7.1f%%"
              % (r["arm"], r["n"], r["ns"], r["mean_strong"], r["se"], r["mean_all"], 100 * r["first"]))
    print()
    if len(table) >= 2:
        a0, a1 = table[0], table[1]
        d = a1["mean_strong"] - a0["mean_strong"]
        pooled = math.sqrt(a0["se"] ** 2 + a1["se"] ** 2) if not (math.isnan(a0["se"]) or math.isnan(a1["se"])) else float("nan")
        print("前两名：%s(%.1f) vs %s(%.1f)  Δ=%+.1f  2×SE=%.1f  ⇒ %s"
              % (a0["arm"], a0["mean_strong"], a1["arm"], a1["mean_strong"], d, 2 * pooled,
                 "**可区分**（按主序列取 %s）" % a0["arm"] if abs(d) >= 2 * pooled
                 else "**不可区分**（进入两半 Pareto 破平）"))
    print()
    print("下一步（§V.66 规则）：")
    print("  ① 主序列：房数 ≥%d 且 **强手房分/房**，但 |Δ| < 2×SE 视为不可区分（上面已算）" % a.min_rooms)
    print("  ② 不可区分 ⇒ 跑这两条，按**两半 Pareto**（两半都不差、至少一半更好）破平：")
    print("     python -X utf8 var/_lowprio_run.py -- python -X utf8 tools/hu_gap_split.py --dir recent --since \"%s\" --by-arm" % a.since)
    print("     python -X utf8 var/_lowprio_run.py -- python -X utf8 var/_seat_h2h.py --since \"%s\" --by-arm --top %d" % (a.since, a.strong_top))
    print("  ③ 再平 ⇒ 第 1 率更高者；④ 再平 ⇒ 最近一役判词为正向者；⑤ 都不理想 ⇒ 最近验证过的基线（不赌未验证组合臂）")
    print("  定案后：写 var/_keeper_strategy.txt，再走 §V.28 三命令（_ready_1024 → tminus_check → _switch_to_official.ps1）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
