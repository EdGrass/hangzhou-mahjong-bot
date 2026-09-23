"""tools/oracle_audit —— 决策级执行验证与进度代理评估（P3b v0）。

输入：run_bot --record-replays 产出的 <gid>.dec.jsonl（每行一条决策记录，
字段见 bot/game.py _dr_payload）。对每条【已执行】（sub=ok）决策：
1) 执行审计：用指定策略重放同一局面 → 动作分歧率/触发统计（防"策略没执行"
   类废测；E 对 E 应恒 0 分歧 = 数据自检）；
2) 进度代理（仅 draw 回合出牌）：弃牌后 13 张的活等待/听牌 1 巡自摸概率
   （河已见剔除，未见图谱按均匀近似）——候选 vs 基准弃牌的代理差汇总。

用法：
  python tools/oracle_audit.py --dirs "var/replays/e4a_*"          # 全部座目录
  python tools/oracle_audit.py --dirs "var/replays/e4a_qinglong" \
      --strategies speedE,speedv        # 指定重放策略（默认 speedE）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.model import my_turn, window_pending  # noqa: E402
from mahjong.shanten import waits  # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten  # noqa: E402


def load_records(dirs):
    """读入决策记录并按 (gid, seat) 排序；同一 (s,p,t,q,a) 重复行只留最后一条。"""
    recs = {}
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.dec.jsonl")):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    if r.get("k") != "d":
                        continue
                    key = (r["g"], r["s"])
                    recs.setdefault(key, []).append(r)
    out = []
    for key in sorted(recs):
        lines = recs[key]
        lines.sort(key=lambda r: int(r.get("q") or 0))
        seen = {}
        for r in lines:
            dedupe = (r.get("p"), r.get("t"), r.get("q"),
                      json.dumps(r.get("a"), sort_keys=True))
            seen[dedupe] = r          # 同键留最后
        out.append((key, sorted(seen.values(),
                                key=lambda r: int(r.get("q") or 0))))
    return out


def rebuild_view(rec):
    god = rec.get("god") or {}
    return {"seat": rec.get("s"), "phase": rec.get("p"),
            "turn": rec.get("t"),
            "responding_seats": list(rec.get("rs") or []),
            "drawn_tile": rec.get("d"), "my_hand": list(rec.get("h") or []),
            "melds": [{"type": m[0], "tile": m[1]} for m in (rec.get("m") or [])],
            "god": {"baotou": bool(god.get("b")),
                    "chain_count": int(god.get("cc") or 0),
                    "piao_count": int(god.get("piao") or 0),
                    "catch_play": bool(god.get("cp"))},
            "offer_tile": rec.get("o"), "river": list(rec.get("r") or [])}


def _seen_counts(hand13, river):
    seen = {}
    for t in list(hand13) + list(river or []):
        seen[t] = seen.get(t, 0) + 1
    return seen


def _proxy(rec, discard_tile):
    """弃牌 d 后的进度代理：向听 / 活等待 / 1 巡自摸概率（近似）。"""
    hand = list(rec["h"] or [])
    if discard_tile not in hand:
        return None
    rem = list(hand)
    rem.remove(discard_tile)
    melds = rec.get("m") or []          # [[type, tile], ...]
    e = len(melds)
    g = sum(1 for m in melds if m and m[0] == "gang")
    if len(rem) != 13 - 3 * e - g:
        return None
    try:
        s = exact_shanten(rem, qidui=(e == 0 and g == 0),
                          exposed_melds=e, gangs=g)
    except ValueError:
        return None
    res = {"s": s, "live_wait": 0, "p1": 0.0}
    if s == 0:
        try:
            ws = waits(rem, exposed_melds=e, gangs=g)
        except ValueError:
            ws = []
        seen = _seen_counts(rem, rec.get("r") or [])
        live = [t for t in ws if seen.get(t, 0) < 4]
        total_unseen = 136 - sum(seen.values())
        num = sum(4 - seen.get(t, 0) for t in live)
        res["live_wait"] = len(live)
        res["p1"] = num / total_unseen if total_unseen else 0.0
    return res


def _action_of(r):
    a = r.get("a")
    return (a or {}).get("action"), (a or {}).get("tile")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True,
                    help="决策记录目录（支持 glob）")
    ap.add_argument("--strategies", default="speedE",
                    help="重放策略（逗号分隔；默认 speedE=执行审计基准）")
    args = ap.parse_args()
    from run_bot import STRATEGY_FACTORIES
    strats = [STRATEGY_FACTORIES[n.strip()]()
              for n in args.strategies.split(",") if n.strip() in STRATEGY_FACTORIES]
    if not strats:
        raise SystemExit("无可用策略: %s" % args.strategies)
    dirs = []
    for d in args.dirs:
        dirs += glob.glob(d)
    games = load_records(sorted(set(dirs)))
    # 执行审计（只统计 sub=ok 的已执行动作）
    div = {s.__class__.__name__: {"n": 0, "diff": 0, "by_phase": {}}
           for s in strats}
    n_exec = 0
    n_draw_discard = 0
    proxy_total = {"n": 0, "delta_p1": 0.0, "n_tenpai": 0,
                   "agree": 0, "disagree": 0, "disagree_p1_sum": 0.0}
    for (gid, seat), recs in games:
        for r in recs:
            if r.get("sub") != "ok":
                continue
            act_name, tile = _action_of(r)
            if act_name is None:
                continue
            n_exec += 1
            view = rebuild_view(r)
            for st in strats:
                name = st.__class__.__name__
                try:
                    mine = st.decide(view)
                except Exception:
                    mine = None
                mname = (mine or {}).get("action") if mine else None
                if mine is not None:
                    div[name]["n"] += 1
                    diff = not (mname == act_name and
                                ((mine or {}).get("tile") or "") == (tile or ""))
                    if diff:
                        div[name]["diff"] += 1
                        ph = r.get("p") or "?"
                        div[name]["by_phase"][ph] = \
                            div[name]["by_phase"].get(ph, 0) + 1
            # 进度代理：draw 回合实际出牌（非抓打圈强迫）对比 E 选张
            if act_name == "discard" and r.get("p") == "draw" and \
                    r.get("t") == r.get("s") and \
                    not view["god"]["catch_play"] and \
                    "SpeedE" in div:
                n_draw_discard += 1
                base = STRATEGY_FACTORIES["speedE"]().decide(view)
                b_tile = (base or {}).get("tile") if base else None
                p_act = _proxy(r, tile)
                p_base = _proxy(r, b_tile) if b_tile else None
                if p_act and p_base and b_tile is not None:
                    proxy_total["n"] += 1
                    dlt = (p_act["p1"] - p_base["p1"]) if p_act["s"] == 0 \
                        and p_base["s"] == 0 else 0.0
                    proxy_total["delta_p1"] += dlt
                    if p_act["s"] == 0:
                        proxy_total["n_tenpai"] += 1
                    if b_tile == tile:
                        proxy_total["agree"] += 1
                    else:
                        proxy_total["disagree"] += 1
                        proxy_total["disagree_p1_sum"] += dlt
    print("== 语料 ==")
    print("games(seat,gid)=%d 已执行动作=%d draw弃牌=%d" %
          (len(games), n_exec, n_draw_discard))
    print("== 执行审计（重放 vs 实际）==")
    for name, d in div.items():
        rate = 100.0 * d["diff"] / d["n"] if d["n"] else 0.0
        print("%-8s 可比动作=%d 分歧=%d (%.1f%%) 按phase=%s" %
              (name, d["n"], d["diff"], rate,
               json.dumps(d["by_phase"], ensure_ascii=False)))
    print("== 进度代理（实际弃牌 vs E 弃牌，仅 draw 自由弃牌）==")
    pt = proxy_total
    if pt["n"]:
        print("n=%d 与E同选=%d 分歧=%d | 分歧组 ΔP1巡自摸均值=%.4f（+为实际更优）" %
              (pt["n"], pt["agree"], pt["disagree"],
               pt["disagree_p1_sum"] / pt["disagree"] if pt["disagree"] else 0.0))
    else:
        print("无数据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
