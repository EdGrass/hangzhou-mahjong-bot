# -*- coding: utf-8 -*-
"""离线复盘门控对比：在**我方真机决策记录**上回放候选策略的窗口判据。

为什么可信：碰/吃窗口由**别家打出什么牌**触发，对我的策略是外生的；策略只决定
「收/过」。因此把另一个门控跑在同一批真实窗口上，是对**门控接受率**的直接测量，
不是 sim 外推。（出牌路径的分布会随策略漂移，故本工具只回答窗口问题。）

数据：var/replays/auto_*/**.dec.jsonl（每行 = 一次真实决策，含手牌/副露/摸牌/
      窗口/最终提交动作）。

用法：
    python -X utf8 tools/offline_replay.py --files 300
    python -X utf8 tools/offline_replay.py --files 300 --cand speedc122 --base speedc073w4
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def melds_from_am(rec):
    """从 dec 记录的 `am` 字段重建**四家副露**（供可见张扣除）。

    为什么需要（R877）：本地 `to_view` 一直把 `all_melds` 写死成 []，
    而实盘视图（`bot/model.py`）是**带的** ⇒ 所有基于 `to_view` 的**离线**工具
    在算 live 进张时**漏扣四家副露**，把死张当活张。
    `am` 格式：长度 4 的列表，每家一个**扁平牌表**（如 [["2w","4w","3w"], ...]）。
    —— 计数只需牌面，不需要分组，故每家封一个 dict 即可。
    """
    am = rec.get("am") or []
    if not (isinstance(am, list) and len(am) == 4):
        return []
    out = []
    for tiles in am:
        tiles = list(tiles or [])
        out.append([{"type": "meld", "tile": tiles[0] if tiles else "", "tiles": tiles}] if tiles else [])
    return out


def to_view(rec):
    """dec 记录 → 策略层 view（字段对齐 bot/model.py 的 snap_view）。"""
    melds = []
    for item in rec.get("m") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            kind, tile = item[0], item[1]
        elif isinstance(item, dict):
            kind, tile = item.get("type") or item.get("kind"), item.get("tile")
        else:
            continue
        if kind in ("chi", "peng", "gang"):
            n = 4 if kind == "gang" else 3
            melds.append({"type": kind, "tile": tile, "tiles": [tile] * n})
    god = rec.get("god") or {}
    return {
        "seat": int(rec.get("s", -1)),
        "phase": rec.get("p") or "",
        "turn": int(rec.get("t", -1)),
        "responding_seats": list(rec.get("rs") or []),
        "my_hand": list(rec.get("h") or []),
        "melds": melds,
        "drawn_tile": rec.get("d"),
        "offer_tile": rec.get("o"),
        "god": {"baotou": bool(god.get("b")), "chain_count": int(god.get("cc") or 0),
                "catch_play": bool(god.get("cp"))},
        "all_melds": melds_from_am(rec),
    }


def draws(files):
    """出牌决策记录（phase=draw 且轮到本人）。"""
    for path in files:
        try:
            fh = open(path, encoding="utf-8")
        except Exception:
            continue
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            if str(rec.get("p")) != "draw":
                continue
            if int(rec.get("t", -1)) != int(rec.get("s", -2)):
                continue
            yield rec


def windows(files, limit_records=None):
    n = 0
    for path in files:
        try:
            fh = open(path, encoding="utf-8")
        except Exception:
            continue
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            if not str(rec.get("p") or "").startswith("response_"):
                continue
            if not rec.get("o"):
                continue
            # 只统计「本人确实有响应权」的窗口（seat ∈ responding_seats）：
            # 其余记录是别家窗口的广播状态，不构成我方决策。
            if int(rec.get("s", -1)) not in (rec.get("rs") or []):
                continue
            n += 1
            if limit_records and n > limit_records:
                return
            yield rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=300, help="抽样多少个 dec 文件")
    ap.add_argument("--base", default="speedc073w4")
    ap.add_argument("--cand", default="speedc122")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少窗口（0=不限）")
    ap.add_argument("--show", type=int, default=6, help="展示几个反转样例")
    ap.add_argument("--phase", choices=("window", "draw"), default="window",
                    help="window=碰/吃窗口判据；draw=出牌选择（比较弃哪张）")
    ap.add_argument("--lowprio", action="store_true",
                    help="把本进程降到 BelowNormal。⚠ 实盘 A/B 期间跑本工具**必须**开（STATUS §9.30/§9.47）")
    args = ap.parse_args()

    if args.lowprio:
        # 实盘期间跑重分析会与 bot 抢 CPU（§9.30 造成过一次 4.4s 出牌超窗；§9.47 又跑出 2×3.6GB）⇒ 必须自降优先级。
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from _lowprio import lower as _lower
            _lower()
        except Exception:
            pass

    from run_bot import STRATEGY_FACTORIES as F
    paths = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
    if not paths:
        sys.exit("未找到 .dec.jsonl 语料")
    random.seed(args.seed)
    paths = random.sample(paths, min(args.files, len(paths)))
    print("抽样 %d 个 dec 文件（全量 %d）" % (len(paths), len(glob.glob(
        os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))))

    base, cand = F[args.base](), F[args.cand]()
    stat = collections.Counter()
    flips = []
    if args.phase == "draw":
        for rec in draws(paths):
            v = to_view(rec)
            try:
                ab, ac = base.decide(v) or {}, cand.decide(v) or {}
            except Exception:
                stat["err"] += 1
                continue
            tb, tc = str(ab.get("tile") or ""), str(ac.get("tile") or "")
            stat["decisions"] += 1
            if ab.get("action") != ac.get("action"):
                stat["action_differs"] += 1
            elif tb != tc:
                stat["tile_differs"] += 1
                bai_kept_b = "白" in [x for x in v["my_hand"] if x != tb]
                bai_kept_c = "白" in [x for x in v["my_hand"] if x != tc]
                stat["cand_keeps_bai"] += 1 if (bai_kept_c and not bai_kept_b) else 0
                if len(flips) < args.show:
                    flips.append((rec, tb, tc))
            else:
                stat["same"] += 1
        n = max(1, stat["decisions"])
        print("\n出牌决策数 %d" % stat["decisions"])
        print("  完全一致 %d (%.1f%%)  tile 不同 %d (%.1f%%)  action 不同 %d (%.1f%%)  异常 %d"
              % (stat["same"], 100.0 * stat["same"] / n, stat["tile_differs"],
                 100.0 * stat["tile_differs"] / n, stat["action_differs"],
                 100.0 * stat["action_differs"] / n, stat["err"]))
        print("  其中候选多保住白：%d" % stat["cand_keeps_bai"])
        for rec, tb, tc in flips:
            print("\n  [出牌不同] %s hand=%s drawn=%s -> %s(基线) vs %s(候选)"
                  % (rec.get("g"), rec.get("h"), rec.get("d"), tb, tc))
        return
    for rec in windows(paths, args.limit or None):
        v = to_view(rec)
        try:
            ab = base.decide(v) or {}
        except Exception:
            stat["base_err"] += 1
            continue
        try:
            ac = cand.decide(v) or {}
        except Exception:
            stat["cand_err"] += 1
            continue
        kb = str(ab.get("action") or "")
        kc = str(ac.get("action") or "")
        stat["windows"] += 1
        stat["phase_" + str(rec.get("p"))] += 1
        # 「可索取窗口」才是有效分母：手上真的够碰 / 有可吃的搭子
        hand = list(rec.get("h") or [])
        offer = rec.get("o")
        if str(rec.get("p")) == "response_peng":
            avail = hand.count(offer) >= 2
        else:
            avail = False
            if offer and offer[-1] in "wbt":
                n, suit = int(offer[0]), offer[1]
                hs = set(hand)
                for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
                    ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
                    if 1 <= a <= 9 and 1 <= b <= 9 and ta in hs and tb in hs:
                        avail = True
                        break
        if avail:
            stat["avail"] += 1
            if kb in ("peng", "chi", "gang"):
                stat["avail_base_meld"] += 1
            if kc in ("peng", "chi", "gang"):
                stat["avail_cand_meld"] += 1
        for tag, k in (("base", kb), ("cand", kc)):
            stat["%s_meld" % tag] += 1 if k in ("peng", "chi", "gang") else 0
        if kb in ("peng", "chi", "gang") and kc in ("peng", "chi", "gang"):
            stat["both"] += 1
        elif kc in ("peng", "chi", "gang") and kb not in ("peng", "chi", "gang"):
            stat["cand_only"] += 1
            if len(flips) < args.show:
                flips.append((rec, kb, kc))
        elif kb in ("peng", "chi", "gang") and kc not in ("peng", "chi", "gang"):
            stat["base_only"] += 1
        else:
            stat["neither"] += 1
        # 记录实际动作（历史策略不一，仅作参考）
        stat["actual_" + str((rec.get("a") or {}).get("action"))] += 1

    w = max(1, stat["windows"])
    print("\n窗口数 %d（碰 %d / 吃 %d）" % (w, stat["phase_response_peng"],
                                          stat["phase_response_chi"]))
    print("  %s 收副露 %d (%.2f%%)" % (args.base, stat["base_meld"], 100.0 * stat["base_meld"] / w))
    print("  %s 收副露 %d (%.2f%%)" % (args.cand, stat["cand_meld"], 100.0 * stat["cand_meld"] / w))
    print("  两者都收 %d / 仅候选收 %d / 仅基线收 %d / 都不收 %d"
          % (stat["both"], stat["cand_only"], stat["base_only"], stat["neither"]))
    print("  引擎/异常: base=%d cand=%d" % (stat["base_err"], stat["cand_err"]))
    if stat["base_meld"]:
        print("  → 副露量变化倍数 %.2fx（候选/基线）"
              % (stat["cand_meld"] / stat["base_meld"]))
    av = max(1, stat["avail"])
    print("\n--- 可索取窗口（够碰/有搭子可吃）为有效分母 ---")
    print("  可索取 %d / 全部 %d (%.1f%%)" % (stat["avail"], w, 100.0 * stat["avail"] / w))
    print("  索取率(收副露/可索取):  基线 %.1f%%   候选 %.1f%%"
          % (100.0 * stat["avail_base_meld"] / av, 100.0 * stat["avail_cand_meld"] / av))
    print("\n  参照：我方真机副露/轮 0.866，前排 1.09-1.32（见 field-audit 报告）")
    for rec, kb, kc in flips:
        print("\n  [反转] %s p=%s hand=%s offer=%s melds=%s -> %s(基线) vs %s(候选)"
              % (rec.get("g"), rec.get("p"), rec.get("h"), rec.get("o"), rec.get("m"), kb, kc))


if __name__ == "__main__":
    main()
