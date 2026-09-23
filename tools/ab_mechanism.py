# -*- coding: utf-8 -*-
"""A/B **机制核对**（manipulation check）：候选在真机上有没有做出预期的行为改变？

⚠ 这**不是判据**。本项目已 9 次证明「行为画像 ↔ 得分」不可迁移（副露/杠/听牌率/张数/爆头率/…）；
本工具只回答一个问题：**干预有没有生效**。
最终采用与否**只**看 `tools/ab_readout.py` 的净胜/小时（当前战役臂那一行）。

逐臂输出（全部只用我方决策记录，不依赖局结果，因此不受 block 文件不完整的影响）：
  房数 / 我方出牌数 / **摸切率** / **平均进张遗憾** / 进张遗憾>0 的占比 / 胡动作数

「进张遗憾」= 最小向听组内最优 live 进张 − 实选弃牌的 live 进张（≥0；单位=张）。
参考基线（8,279 个真机窗口）：合计 **5.09 张**，其中 s=1 为 6.55、s=2 为 6.41；
`bot/speedc132.py` 把它降到 **0.59**（非听牌段 0.01–0.09）⇒ 若 A/B 房里该值没降，说明干预没生效。

用法：
    python -X utf8 tools/ab_mechanism.py            # 用 var/.ab_mode 的当前战役臂与起始时间
    python -X utf8 tools/ab_mechanism.py --limit 40  # 只看最近 40 个房目录
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, sys, multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ME = "u_7a3fba48d70b"
AB = os.path.join(ROOT, "var", ".ab_mode")


def _campaign():
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return [None], None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    return [str(x) for x in (arms or []) if x], cfg.get("started")


def _melds_of(rec):
    m = rec.get("m") or []
    ex = len(m)
    gg = 0
    for x in m:
        kind = x[0] if isinstance(x, (list, tuple)) and x else (x.get("type") if isinstance(x, dict) else None)
        if kind == "gang":
            gg += 1
    return ex, gg


def work_room(args):
    d, st, my = args
    from mahjong.shanten_exact import shanten as ex
    from bot.c069routes import ukeire_counts
    disc = tsumo = 0
    regrets = []
    hus = 0
    breakpair = 0          # 打出的牌在手里有 ≥2 张（拆对；会伤七对路线）
    pairs_after = 0.0
    tenpai = 0             # 打完之后 13 张已是听牌
    waits_sum = 0          # 听牌时的听牌张数之和（用于 E[张|听]）
    tenpai_n = 0
    for p in glob.glob(os.path.join(d, "*.dec.jsonl")):
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            ph = str(r.get("p") or "")
            act = (r.get("a") or {}).get("action")
            if act == "hu":
                hus += 1
            if ph != "draw" or act != "discard":
                continue
            hand = list(r.get("h") or [])
            ex_, gg = _melds_of(r)
            if len(hand) != 14 - 3 * ex_ - gg:
                continue
            disc += 1
            if r.get("d") and act == "discard" and (r["a"].get("tile") == r.get("d")):
                tsumo += 1
            _t = r["a"].get("tile")
            if _t and hand.count(_t) >= 2:
                breakpair += 1
            _rem = list(hand)
            try:
                _rem.remove(_t)
                pairs_after += sum(1 for _k, _n in collections.Counter(_rem).items()
                                   if _k != "白" and _n >= 2)
                # 因果链核对：进张改善是否真的转化成「更容易听牌」
                from mahjong.shanten_exact import shanten as _ex
                from mahjong.shanten import waits as _waits
                _s = _ex(list(_rem), qidui=(ex_ == 0 and gg == 0),
                         exposed_melds=ex_, gangs=gg, god_meld=True)
                tenpai_n += 1
                if _s == 0:
                    tenpai += 1
                    try:
                        waits_sum += len(_waits(list(_rem), exposed_melds=ex_, gangs=gg))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                cands = []
                for t in sorted(set(hand)):
                    rem = list(hand)
                    rem.remove(t)
                    cands.append((t, rem, ex(list(rem), qidui=(ex_ == 0 and gg == 0),
                                             exposed_melds=ex_, gangs=gg, god_meld=True)))
                smin = min(c[2] for c in cands)
                grp = [c for c in cands if c[2] == smin]
                chosen = [c for c in grp if c[0] == r["a"].get("tile")]
                if not chosen or smin == 0:
                    continue          # 听牌段本候选设计上不动，不计入
                best = max(ukeire_counts(list(c[1]))[1] for c in grp)
                regrets.append(best - ukeire_counts(list(chosen[0][1]))[1])
            except Exception:
                continue
    return st, disc, tsumo, regrets, hus, breakpair, pairs_after, tenpai, tenpai_n, waits_sum


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--arms", default=None, help="逗号分隔；默认取 .ab_mode")
    ap.add_argument("--limit", type=int, default=0, help="只看最近 N 个房目录")
    ap.add_argument("--jobs", type=int, default=min(12, os.cpu_count() or 4))
    a = ap.parse_args(argv)
    arms, started = _campaign()
    if a.arms:
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    since = a.since or started
    r2s, r2ts = {}, {}
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        if d.get("room"):
            r2s[d["room"]] = d.get("strategy") or "?"
            r2ts[d["room"]] = d.get("ts") or ""
    jobs = []
    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")), key=os.path.getmtime)
    if a.limit:
        dirs = dirs[-a.limit:]
    for d in dirs:
        decs = glob.glob(os.path.join(d, "*.dec.jsonl"))
        if not decs:
            continue
        rid = my = None
        for p in decs:
            for ln in io.open(p, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                rid = rid or (r.get("g") or "").split("_r")[0]
                if my is None and r.get("s") is not None:
                    my = int(r["s"])
                break
            if rid and my is not None:
                break
        st = r2s.get(rid)
        if not st or (arms and st not in arms) or (since and (r2ts.get(rid) or "") < since):
            continue
        jobs.append((d, st, my))
    A = collections.defaultdict(lambda: {"rooms": 0, "disc": 0, "tsumo": 0, "hus": 0,
                                          "reg": [], "bp": 0, "pairs": 0.0,
                                          "tp": 0, "tpn": 0, "ws": 0})
    with mp.Pool(a.jobs) as pool:
        for (st, disc, tsumo, regrets, hus, bp, pa, tp, tpn, ws) in pool.imap_unordered(work_room, jobs, chunksize=2):
            s = A[st]
            s["rooms"] += 1; s["disc"] += disc; s["tsumo"] += tsumo
            s["hus"] += hus; s["reg"].extend(regrets)
            s["bp"] += bp; s["pairs"] += pa
            s["tp"] += tp; s["tpn"] += tpn; s["ws"] += ws
    print("A/B 机制核对（since=%s，臂=%s）—— ⚠ 仅作「干预是否生效」，不是判据"
          % (since or "-", arms))
    print("%-14s %6s %9s %9s %11s %11s %8s %8s %8s %9s" % ("arm", "rooms", "我方出牌", "摸切率",
                                                               "平均进张遗憾", ">0 占比", "拆对率",
                                                               "对子数", "听牌率", "E[张|听]"))
    import statistics
    for st in (arms or sorted(A)):
        s = A.get(st)
        if not s or not s["disc"]:
            print("%-14s %6d  尚无可比房间" % (st, 0)); continue
        reg = s["reg"]
        mean_reg = statistics.mean(reg) if reg else float("nan")
        share = 100.0 * sum(1 for x in reg if x > 0) / len(reg) if reg else 0.0
        print("%-14s %6d %9d %8.1f%% %11.2f %10.1f%% %7.1f%% %8.2f %8.1f%% %9.2f" % (
            st, s["rooms"], s["disc"], 100.0 * s["tsumo"] / max(s["disc"], 1),
            mean_reg, share, 100.0 * s["bp"] / max(s["disc"], 1),
            s["pairs"] / max(s["disc"], 1),
            100.0 * s["tp"] / max(s["tpn"], 1), s["ws"] / max(s["tp"], 1)))
    print("\n参考：进张遗憾（8,279 个真机窗口）基线 **5.09 张** / speedc132 **0.59**；"
          "听牌率参考（全语料）我方 ~26% / 前排 ~30.5%。")
    print("因果链核对：**进张改善是否真的抬高了听牌率**——若某臂进张遗憾降到 ~0 而听牌率没动，"
          "说明这条链断了，应停止该臂而不是等分数。")
    print("拆对率参考（2,828 个门清窗口离线回放）：基线 **1.8%**、speedc132 **10.4%**")
    print("  ⇒ 拆对会削弱**七对路线**（七对 ×2 / 七对+爆头 ×4；离线七对向听 3.072 → 3.145）。")
    print("  这是 C132 的已知代价，必须由分数（ab_readout）而不是本表来裁决。")
    print("⇒ 若 c132 房的这个数没降到 <1.5，说明干预没生效，应立刻停 A/B 而不是等分数。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
