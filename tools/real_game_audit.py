# -*- coding: utf-8 -*-
"""real_game_audit —— 真机语料的全信息审计（四家手牌重建）。

从 `var/replays/server|recent/*.json`（门户 `blocks` 分块**含四家手牌**）重建每一手，
在**每次自己出牌之后**（= 该巡结束、等待下一次摸牌）计算该家当时的手牌指标。

输出（逐玩家 / 逐策略）：
  听牌率   前 8 巡里处于听牌（向听=0）的比例
  张|听    听牌时的平均听牌张数（等待宽度）
  爆头|听  听牌态里「摸任意一张即胡」的比例（本作爆头 = 番 ×2，且等于必胜）
  胡/机会  自摸机会的实现率 = 胡数 / 「摸到手的牌能胡」的次数 —— **<100% 即为弃胡（C036）**
  庄溢价   E[分|庄] − E[分|闲]

⚠ **效力边界（2026-09-15 实测，务必读完再用）**

- **跨玩家**：听牌率与真机胜率相关 **+0.933**（61 名 ≥400 局玩家，2,444 个真机复盘）；
  我方 26.0% / 胜率 24.7%，前排 30.5% / 30–33%。分层后可见差距几乎**全部**来自**副露数分布**
  （我方 ex=0 占 61.8% vs 前排 50.8%）；**同等副露下我方与胜率前 20 几乎逐格相同**
  （ex=0 听牌 13.5% vs 13.2%；ex=2 68.3% vs 69.5%；张|听 4.87/4.90/5.39 vs 4.94/4.92/5.46）。
- **同族（我方策略之间）**：听牌画像**不能**稳定预测胜率 ——
  `speedc073w4` 听牌 27.3% / 张|听 5.26 却只有 24.3% 胜率，`speedtugh` 27.9% / 5.19 只有 23.6%，
  而 `speedtugc` 26.6% / 5.13 反而 25.4%；但两者的**房数只有 880 / 640**（胜率 SE ≈1.5–1.7pp），
  差异只有 ~1σ ⇒ **既没证明也没否证**。
⇒ 结论：**跨玩家相关 ≠ 因果靶标**（与 `副露/轮` +0.491、`杠/轮` +0.242、`庄占比` +0.914 同形；
本项目这类相关已被否证 4 次）。**禁止**把听牌率当优化目标调参；它只能用来**描述画像位置**，
或作为**同房配对**的辅助证据。

用法：
    python -X utf8 tools/real_game_audit.py               # 逐玩家
    python -X utf8 tools/real_game_audit.py --by-strategy # 按我方历史策略分组
    python -X utf8 tools/real_game_audit.py --top 16
    python -X utf8 tools/real_game_audit.py --limit 400   # 只取最近 N 个复盘文件（调试用）
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys, multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ME = "u_7a3fba48d70b"
_SMAP = {}
MAX_TURN = 8          # 只看前 8 巡（早期巡次选择效应最小）


def _rounds_of(d):
    """把同一局的所有 block 串起来（start_hands 只在每局第一个 block 出现）。"""
    out, cur = [], None
    for b in d.get("blocks") or []:
        sh = b.get("start_hands")
        if sh and any(isinstance(x, (list, tuple)) for x in sh):
            cur = {"hands": [list(x) if isinstance(x, (list, tuple)) else [] for x in sh],
                   "nm": [0] * 4, "ng": [0] * 4, "turn": [0] * 4}
            out.append((cur, b.get("events") or []))
            continue
        if cur is not None:
            out.append((cur, b.get("events") or []))
    return out


def work(path, only_seat=None):
    """only_seat: 只统计该 user_id 的一席（用于 --by-strategy 把我方历史策略分组）。
    返回 ((A, wins)) —— A: name/strategy -> [turns,tenpai,wsum,baotou,opps,rounds,ptsD,nD,ptsND,nND]"""
    from mahjong.shanten_exact import shanten as exact_shanten
    from mahjong.shanten import waits
    from mahjong.hu import is_baotou, is_win
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    # ★ 2026-09-17 修：锦标赛复盘目录里带 `manifest.json`（内容是 JSON **list**）⇒
    #   旧实现直接 `d.get("seats")` 会 AttributeError ⇒ 整个审计崩掉（今晚赛后就踩这个）。
    if not isinstance(d, dict):
        return None
    if only_seat is not None and only_seat not in [(x.get("user_id") or "") for x in (d.get("seats") or [])]:
        return None
    seats = d.get("seats") or []
    names = [s.get("name") or "?" for s in seats]
    if len(names) != 4:
        return None
    # 每人: [turns, tenpai, wsum, baotou, opps, rounds, pts_dealer, n_dealer, pts_non, n_non]
    A = collections.defaultdict(lambda: [0] * 10)
    wins = collections.Counter()
    keep = None
    if only_seat is not None:
        _seats = d.get("seats") or []
        for _i, _x in enumerate(_seats):
            if (_x.get("user_id") or "") == only_seat:
                keep = _i
        if keep is None:
            return None
    for r in d.get("rounds") or []:
        sc = r.get("scores") or []
        if len(sc) != 4:
            continue
        dl, w = r.get("dealer"), r.get("winner")
        idxs = range(4) if keep is None else (keep,)
        for i in idxs:
            nm = names[i]
            a = A[nm]; a[5] += 1
            if dl == i: a[6] += sc[i]; a[7] += 1
            else: a[8] += sc[i]; a[9] += 1
            if w == i: wins[nm] += 1
    for cur, events in _rounds_of(d):
        # ⚠ 2026-09-16 修：「前 8 巡」= 该局我方**第 1~8 次出牌**。
        # 旧实现 `turn = [0]*4` 在**每个 block** 重置（一局平均 ~2 个 block）
        # ⇒ 把一局后段的出牌也当成"前 8 巡"，听牌率被显著高估（§9.19/9.20）。
        turn = cur.setdefault("turn", [0] * 4)
        hands, nm, ng = cur["hands"], cur["nm"], cur["ng"]
        for e in events:
            t, s = e.get("type"), e.get("seat")
            if s is None or s < 0:
                continue
            if t == "round_ended":
                cur["hands"] = [[], [], [], []]      # 该局结束
                cur["turn"] = [0] * 4
                break
            if t == "tile_drawn":
                hands[s].append(e["tile"])
                if keep is None or s == keep:
                    ex, gg = nm[s] + ng[s], ng[s]
                    try:
                        if is_win(list(hands[s]), exposed_melds=ex, gangs=gg): A[names[s]][4] += 1
                    except Exception:
                        pass
            elif t == "tile_discarded":
                if e["tile"] in hands[s]: hands[s].remove(e["tile"])
                else: continue
                turn[s] += 1
                if turn[s] <= MAX_TURN and (keep is None or s == keep):
                    ex, gg = nm[s] + ng[s], ng[s]
                    try:
                        shv = exact_shanten(list(hands[s]), qidui=(ex == 0 and gg == 0),
                                            exposed_melds=ex, gangs=gg)
                    except Exception:
                        continue
                    a = A[names[s]]; a[0] += 1
                    if shv == 0:
                        a[1] += 1
                        try:
                            a[2] += len(waits(list(hands[s]), exposed_melds=ex, gangs=gg))
                            if is_baotou(list(hands[s]), allow_qidui=(ex == 0 and gg == 0),
                                         exposed_melds=ex, gangs=gg): a[3] += 1
                        except Exception:
                            pass
            elif t == "peng":
                for _ in range(2):
                    if e["tile"] in hands[s]: hands[s].remove(e["tile"])
                    else: break
                nm[s] += 1
            elif t == "chi":
                used = list((e.get("data") or {}).get("tiles") or [])
                if e["tile"] in used: used.remove(e["tile"])
                for x in used:
                    if x in hands[s]: hands[s].remove(x)
                    else: break
                nm[s] += 1
            elif t == "gang":
                kind = (e.get("data") or {}).get("kind")
                if kind == "bu":
                    if e["tile"] in hands[s]: hands[s].remove(e["tile"])
                    nm[s] -= 1; ng[s] += 1
                else:
                    for _ in range(4 if kind == "an" else 3):
                        if e["tile"] in hands[s]: hands[s].remove(e["tile"])
                        else: break
                    ng[s] += 1
    return dict(A), dict(wins)


def _work_strategy(args):
    """按「房→策略」归组的 worker：把我方那一席的统计挂到策略名下。
    注意 Windows 用 spawn 起子进程 ⇒ 模块全局不会继承，策略名必须随参数传入。"""
    path, me, st = args
    if not st:
        return None
    res = work(path, only_seat=me)
    if not res:
        return None
    A, W = res
    agg = collections.defaultdict(lambda: [0] * 10)
    tot = 0
    for k, v in A.items():
        for i in range(10):
            agg[st][i] += v[i]
        tot += v[5]
    return dict(agg), {st: sum(W.values())}


def row(nm, a, w, label=None, min_rounds=400):
    """⚠ min_rounds 不是可有可无的参数：正式赛一场（M=10 × Rounds=16）只有 **16 轮**，
    用默认的 400 会把**每一个参赛者（包括我们自己）**都过滤掉 ⇒ 赛后审计会得到空表。
    赛后用 `--min-rounds 8`（或 4）才能看到数据。"""
    t, tp, ws, bt, op = a[0], a[1], a[2], a[3], a[4]
    rd, pd, nd, pn, nn = a[5], a[6], a[7], a[8], a[9]
    if t < min_rounds or rd < min_rounds:
        return None
    return {"name": label or nm, "rounds": rd, "turns": t,
            "tp": 100.0 * tp / t, "w": ws / max(tp, 1), "bt": 100.0 * bt / max(tp, 1),
            "take": 100.0 * w / max(op, 1), "opps": op, "wins": w,
            "win": 100.0 * w / rd,
            "prem": (pd / nd - pn / nn) if nd and nn else 0.0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--by-strategy", action="store_true", help="按 var/auto_ranking.jsonl 的策略归属分组")
    ap.add_argument("--top", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=min(12, os.cpu_count() or 4))
    ap.add_argument("--min-rounds", type=int, default=400,
                    help="进入表格所需的最少轮数/巡数（正式赛一场只有 16 轮 ⇒ 用 8 或 4；默认 400 是阶梯语料口径）")
    ap.add_argument("--dirs", default="server,recent",
                    help="复盘子目录（逗号分隔，相对 var/replays/）；正式赛后用 official_1024_* 做赛后审计")
    a = ap.parse_args(argv)
    _dirs = [x.strip() for x in str(a.dirs).split(",") if x.strip()]
    fs = []
    for _d in _dirs:
        fs += [p for p in glob.glob(os.path.join(ROOT, "var/replays", _d, "*.json"))
               if os.path.basename(p) != "manifest.json"]
    fs = sorted(set(fs), key=os.path.getmtime)
    if a.limit:
        fs = fs[-a.limit:]
    smap = {}
    if a.by_strategy:
        for ln in open(os.path.join(ROOT, "var/auto_ranking.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if ln:
                d = json.loads(ln)
                if d.get("room"):
                    smap[d["room"]] = d.get("strategy") or "?"
    _SMAP.clear(); _SMAP.update(smap)
    totals = collections.defaultdict(lambda: [0] * 10)
    win = collections.Counter()
    with mp.Pool(a.jobs) as pool:
        for res in pool.imap_unordered(work, fs, chunksize=8):
            if not res:
                continue
            A, W = res
            for k, v in A.items():
                q = totals[k]
                for i in range(10):
                    q[i] += v[i]
            for k, v in W.items():
                win[k] += v
    # 逐策略模式：只统计我方那一席，按「房 → 策略」归属分组
    if a.by_strategy:
        args = [(p, ME, smap[os.path.basename(p).split("_r")[0]]) for p in fs
                if os.path.basename(p).split("_r")[0] in smap]
        tot2 = collections.defaultdict(lambda: [0] * 10)
        win2 = collections.Counter()
        with mp.Pool(a.jobs) as pool:
            for res in pool.imap_unordered(_work_strategy, args, chunksize=8):
                if not res:
                    continue
                A, W = res
                for k, v in A.items():
                    q = tot2[k]
                    for i in range(10):
                        q[i] += v[i]
                for k, v in W.items():
                    win2[k] += v
        rows2 = [r for k, v in tot2.items() if (r := row(k, v, win2[k], label=k, min_rounds=a.min_rounds))]
        rows2.sort(key=lambda r: -r["win"])
        print("逐策略（我方历史，语料 %d 个文件命中 %d 个）：" % (len(fs), len(args)))
        print("%-16s %7s %8s %8s %9s %9s %9s %8s" % (
            "strategy", "rounds", "胜率", "听牌率", "张|听", "爆头|听", "胡/机会", "庄溢价"))
        for r in rows2:
            print("%-16s %7d %7.1f%% %7.1f%% %9.2f %8.1f%% %8.1f%% %+8.2f" % (
                r["name"], r["rounds"], r["win"], r["tp"], r["w"], r["bt"], r["take"], r["prem"]))
        print("\n⚠ 不要把本表当选择依据：同族内听牌画像与胜率**不单调**")
        print("   （c073w4/27.3%、tugh/27.9% 的听牌率高于 tugc/26.6%，胜率反而更低；但 n=880/640 只有 ~1σ）")
        print("   ⇒ 真机策略选择仍以 tools/ab_readout.py 的「净胜/小时」为准。")
        return 0
    rows = [r for k, v in totals.items() if (r := row(k, v, win[k], min_rounds=a.min_rounds))]
    rows.sort(key=lambda r: -r["win"])
    print("语料 %d 个复盘文件（%s）；逐玩家（>=%d 局且 >=%d 巡）共 %d 人" % (len(fs), ",".join(_dirs), a.min_rounds, a.min_rounds, len(rows)))
    print("%-22s %7s %8s %8s %9s %9s %9s %8s" % ("name", "rounds", "胜率", "听牌率", "张|听", "爆头|听", "胡/机会", "庄溢价"))
    for r in rows[:a.top]:
        print("%-22s %7d %7.1f%% %7.1f%% %9.2f %8.1f%% %8.1f%% %+8.2f" % (
            r["name"][:20], r["rounds"], r["win"], r["tp"], r["w"], r["bt"], r["take"], r["prem"]))
    me = [r for r in rows if r["name"] == "EdGrass"]
    if me:
        r = me[0]
        print("-" * 100)
        print("%-22s %7d %7.1f%% %7.1f%% %9.2f %8.1f%% %8.1f%% %+8.2f" % (
            "EdGrass(我方)", r["rounds"], r["win"], r["tp"], r["w"], r["bt"], r["take"], r["prem"]))
        rank = rows.index(r) + 1
        print("按胜率排名 %d/%d；按 胡/机会 排名 %d/%d" % (
            rank, len(rows),
            sorted(rows, key=lambda x: -x["take"]).index(r) + 1, len(rows)))
    print("\n注：听牌率跨玩家与胜率强相关(+0.933)，但同族内不能稳定预测胜率（样本 ~1σ，未证未伪），"
          "且本项目同类「行为画像↔得分」相关已被否证 4 次；只能当画像描述，不要当优化目标。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
