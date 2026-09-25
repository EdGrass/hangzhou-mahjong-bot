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
import argparse, collections, glob, io, json, math, os, statistics, subprocess, sys

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
                     int(mine[0].get("rank") or 0), strong, d.get("room") or ""))

    by = collections.defaultdict(lambda: {"all": [], "strong": [], "first": 0})
    for arm, score, rank, strong, _room in rows:
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
    # ★ R1512：把「对手强度」放进同一张读数里（**只加读数，不改排序与阈值**）。
    #   为什么：三臂是 round-robin 开的，房数头对称但**桌强**仍可能不对称；
    #   §V.66 的主序列用“强手房”分层就是为了控这个，而读数里直接看到对手强度能避免“把桌差当策略差”。
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from opp_strength import load_rows as _lr, opponent_strength as _os, slope as _sl
        _rows = _lr(os.path.join(ROOT, "var", "auto_ranking.jsonl"))
        _opp = _os(_rows)
        _pts = []
        _pts_beta = []   # ★ β 用**全样本**估（窗口内的 17 房估不稳：实测 β=-4.07 vs 全样本 -0.84）
        _all = []
        for _d in _rows:
            _rk2 = _d.get("ranking") or []
            _me2 = next((x for x in _rk2 if x.get("user_id") == a.me), None)
            _o2 = _opp.get(_d.get("room"))
            if _d.get("status") == "finished" and _me2 is not None and _o2 is not None and len(_rk2) == 4:
                _ot2 = [x.get("total_score") or 0 for x in _rk2 if x.get("user_id") != a.me]
                _all.append(((_me2.get("total_score") or 0) - sum(_ot2) / 3.0, _o2))
            if _d.get("status") != "finished" or (_d.get("ts") or "") < a.since:
                continue
            _rk = _d.get("ranking") or []
            _me = next((x for x in _rk if x.get("user_id") == a.me), None)
            if _me is None or len(_rk) != 4:
                continue
            _o = _opp.get(_d.get("room"))
            if _o is None:
                continue
            _oth = [x.get("total_score") or 0 for x in _rk if x.get("user_id") != a.me]
            _net = (_me.get("total_score") or 0) - sum(_oth) / 3.0
            _strong = any(u in top for u in (x.get("user_id") for x in _rk)
                          if u and u != a.me)
            _pts.append((_d.get("strategy") or "?", _net, _o, _strong))
            _pts_beta = _all
        if _pts:
            _beta = _sl([x[1] for x in _pts_beta], [x[0] for x in _pts_beta]) if len(_pts_beta) >= 20 else float("nan")
            _gmean = (sum(x[1] for x in _all) / len(_all)) if _all else 0.0   # ★ 基准=全样本桌强均值（与 `_campaign_strength` 同口径）
            print("对手强度（因果口径，只作读数；β=%+.3f 分/分；基准=全样本桌强均值 %+.1f）：" % (_beta, _gmean))
            print("  %-24s %5s %12s %12s %14s" % ("臂", "房", "桌强均值", "强手房桌强", "桌强调整后净胜"))
            for _arm in [r["arm"] for r in table]:
                _xs = [x for x in _pts if x[0] == _arm]
                if not _xs:
                    continue
                _m = sum(x[2] for x in _xs) / len(_xs)
                _ms = [x[2] for x in _xs if x[3]]
                _net = sum(x[1] for x in _xs) / len(_xs)
                _adj = _net - _beta * (_m - _gmean)
                print("  %-24s %5d %12.1f %12s %14.1f"
                      % (_arm, len(_xs), _m, ("%.1f" % (sum(_ms) / len(_ms))) if _ms else "—", _adj))
            print("  （提示：若各臂桌强差异大，先看调整后列与两层强手房读数，再按 §V.66 序列定案。）")
    except Exception as _e:
        print("（对手强度读数不可得：%s）" % str(_e)[:60])
    print()
    if len(table) >= 2:
        a0, a1 = table[0], table[1]
        d = a1["mean_strong"] - a0["mean_strong"]
        pooled = math.sqrt(a0["se"] ** 2 + a1["se"] ** 2) if not (math.isnan(a0["se"]) or math.isnan(a1["se"])) else float("nan")
        print("前两名：%s(%.1f) vs %s(%.1f)  Δ=%+.1f  2×SE=%.1f  |z|=%.2f  ⇒ %s"
              % (a0["arm"], a0["mean_strong"], a1["arm"], a1["mean_strong"], d, 2 * pooled,
                 (abs(d) / pooled) if pooled else float("nan"),
                 "**可区分**（按主序列取 %s）" % a0["arm"] if abs(d) >= 2 * pooled
                 else "**不可区分**（进入两半 Pareto 破平）"))
        # ★ R1505：把“不可区分”的读法写进输出（**不改任何阈值**）
        print("   〈R1505 读数〉|z|≥2.0 = 主序列可区分；1.5≤|z|<2.0 = 与【役门禁】同档但未过选臂口径；|z|<1.5 = 连门禁口径也不显著。")
        print("   〈R1505 读数〉**不可区分 ≠ 没差别**：强手房分/房池化 SD≈129 分/房 ⇒ 80 房/臂时 MDE≈41 分（R1501/R1505 实测），"
              "而实测臂间差只有 22~38 分 ⇒ 这根尺子本来就量不出。必须按下面的 ② 两半 Pareto 读。")
    # ★ R1518：**役 5 的两层否决必须出现在决策材料里**。
    #   为什么：§★追加写着“任一层任一列 ≤ −2×SE ⇒ 不采用”，但它只在读卡/命令里（`_adopt_pair` 只对役 3→4 调用）⇒
    #   10/5 读提案的人不跑那条命令就看不到。这里就地跑一次（**只作读数，不改任何排序/阈值**）。
    if len(table) >= 2:
        try:
            _a0, _a1 = table[0], table[1]
            _p = subprocess.run([sys.executable, "-X", "utf8",
                                 os.path.join(ROOT, "var", "_strong_veto.py"),
                                 "--since", a.since, "--baseline", _a0["arm"],
                                 "--candidate", _a1["arm"]],
                                cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=600)
            _tail = [x for x in (_p.stdout or "").strip().splitlines() if x.strip()][-4:]
            print()
            print("否决预检（强手房两层，只作读数；VETO 则按预登记**不采用该候选**）：")
            print("  %s → %s（rc=%s）" % (_a0["arm"], _a1["arm"], _p.returncode))
            for _l in _tail:
                print("    " + _l)
        except Exception as _e:
            print()
            print("（否决预检不可得：%s）" % str(_e)[:70])
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
