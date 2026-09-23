# -*- coding: utf-8 -*-
"""ab_winrate —— A/B 两臂的**胜率读数**（比"净胜/房"敏感一个数量级的判据）。

## 为什么需要它（这是本项目最重要的一次功率修正）

`ab_readout.py` 用「净胜/房」判 A/B，房级 SD ≈145 原始分（SD(净胜)≈194）⇒ 判 ±20 分/房要 **~100 房/臂**
（≈2.2 天）。但排行榜**就是胜率榜**（只能自摸）：分/局 = 胜率×均胡分 − 失分率×均失分，
且**均失分跨玩家近乎常数** ⇒ **胜率是那个"真信号"，分数只是它的噪声放大器**。

胜率是 0/1 变量，每房 80 局、每局 4 家（我们一席）⇒ 5,000 局的胜率 SE = sqrt(.25*.75/5000) ≈ **0.61pp**，
而"房级"间接反推的 SE 是 **1.26pp**（SD=145/√173/17.6）⇒ **按局测比按房测敏感 2 倍**：
判 **+2pp** 需要 ≈**100 房/臂**（按房）/ ≈**28 房/臂**（按局）。
本工具就是那条"按局"的读数，用来**独立复核** `ab_readout` 的结论。

## 口径（与 ab_readout 严格对齐，别改）

- **胜率 = 自摸胡牌率**（`round_ended.draw == False` 且 winner 是我方）——与排行榜口径一致（只能自摸）；
- 数据源 = 门户 `var/replays/{server,recent}/*.json`（每文件 = 一局），房间→策略来自 `var/auto_ranking.jsonl`；
- **一局的 rounds 台账**（`data["rounds"]`）与 **blocks 事件流**的 hu 计数必须一致（工具自己断言，不一致会报）。

**⚠ 效力边界**：胜率是 0/1 变量，但**同一房内 80 局不独立**（牌桌固定、对手固定）
⇒ 直接二项 SE **可能低估**；本工具同时打印两种 SE（按局二项 / 按房 cluster-robust），
判定时取**更保守**的那个。看 `--verbose` 可打印房级明细。

用法：
    python -X utf8 tools/ab_winrate.py                     # 当前战役两臂
    python -X utf8 tools/ab_winrate.py --arms a,b --since "2026-09-16 00:48:02"
    python -X utf8 tools/ab_winrate.py --verbose
"""
from __future__ import annotations
import argparse, collections, glob, io, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ME = "u_7a3fba48d70b"
AB = os.path.join(ROOT, "var", ".ab_mode")


def campaign():
    """读 var/.ab_mode → (臂列表, started)。与 ab_readout 同口径。"""
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return [], None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    return [str(x) for x in (arms or []) if x], cfg.get("started")


def strategy_map():
    """room_id -> (strategy, ts)。同 `mech_mix`，后写覆盖先写。"""
    out = {}
    p = os.path.join(ROOT, "var", "auto_ranking.jsonl")
    if not os.path.exists(p):
        return out
    for ln in io.open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("room"):
            out[d["room"]] = (d.get("strategy") or "?", d.get("ts") or "")
    return out


def scan_rounds(d):
    """纯函数：返回 (我方座位号, per-round 列表, 自检通过?)。

    每项 = dict(win=bool, fan=int, baotou=bool, dealer=bool, score=int)
    自检：事件流里的 round_ended 数 == len(d["rounds"])（口径不一致就返回 ok=False）。
    """
    ids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
    if len(ids) != 4 or ME not in ids:
        return None, [], True
    me = ids.index(ME)
    recs = []
    for b in d.get("blocks") or []:
        for e in b.get("events") or []:
            if e.get("type") != "round_ended":
                continue
            data = e.get("data") or {}
            sc = data.get("scores") or []
            if len(sc) != 4:
                continue
            det = [str(x) for x in (data.get("detail") or [])]
            recs.append(dict(
                win=bool(isinstance(e.get("seat"), int) and e["seat"] == me and not data.get("draw")),
                fan=int(data.get("fan") or 0),
                baotou=("爆头" in det),
                dealer=(data.get("dealer") == me),
                score=int(sc[me]),
            ))
    total = len(d.get("rounds") or [])
    return me, recs, (len(recs) == total)


def room_differential(recs, opp):
    """纯函数：一房的「我方胜率 − 同房三对手的合并胜率」。opp=(对手总胡数, 对手总轮数)。

    ⚠ **它不是更敏感的判据**（2026-09-16 曾一度误记，见 STATUS §4c-33 的撤回声明）：
    忽略流局时有恒等式 `d = (4p − 1)/3`（胡牌只能出在我方或三个对手之一）⇒ d 与 p 是同一个量的
    线性变换，`SD(d) = (4/3)·SD(p)`（实测 7.25pp vs 6.53pp，扣流局后吻合）⇒ 用它判效应**需要更多房**
    （+1.5pp：297 房 → 366 房）。保留它的用途只有两个：
      ① **零假设标尺**：对手胜率的期望是 (1−p)/3，实测偏离 0 说明这一池子里我们与对手的强弱差；
      ② **展示/记账**：读数时给一个"对手在同一批房里打得怎么样"的直观参照。
    设计判据请用 `win`（原始胜率）与 `ab_readout`（净胜/房）。
    """
    n = len(recs)
    if not n or not opp or not opp[1]:
        return None
    mine = sum(1 for r in recs if r["win"]) / float(n)
    theirs = opp[0] / float(opp[1])
    return mine - theirs


def collect(arms, since=None, dirs=("server", "recent")):
    """返回 {arm: {'rooms': {room: [recs]}}}"""
    smap = strategy_map()
    out = {a: {"rooms": collections.OrderedDict()} for a in arms}
    for dd in dirs:
        for p in glob.glob(os.path.join(ROOT, "var", "replays", dd, "*.json")):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            gid = d.get("game_id") or ""
            room = gid.split("_r")[0]
            info = smap.get(room)
            if not info:
                continue
            st, ts = info
            if st not in out:
                continue
            if since and ts < since:
                continue
            me, recs, ok = scan_rounds(d)
            if me is None or not recs or not ok:
                continue
            blk = out[st]
            blk["rooms"].setdefault(room, []).extend(recs)
            blk.setdefault("opp", [0, 0])
            blk.setdefault("opp_by_room", {})
            _po = blk["opp_by_room"].setdefault(room, [0, 0])
            for b in d.get("blocks") or []:
                for e in b.get("events") or []:
                    if e.get("type") != "round_ended":
                        continue
                    data = e.get("data") or {}
                    if len(data.get("scores") or []) != 4:
                        continue
                    blk["opp"][1] += 3
                    _po[1] += 3
                    if isinstance(e.get("seat"), int) and 0 <= e["seat"] < 4 and not data.get("draw") and e["seat"] != me:
                        blk["opp"][0] += 1
                        _po[0] += 1
    return out


def summarize(data):
    """纯函数：把 {arm: {'rooms': {room: recs}}} 折成统计量。

    返回 {arm: dict(rounds, wins, win, se_binom, se_cluster, rooms, room_win_mean, ...)}
    se_cluster = 房级 cluster-robust SE = stdev(每房胜率) / sqrt(房数)（更保守，含房内相关）。
    """
    res = {}
    for arm, blk in data.items():
        per_room = []
        per_room_diff = []
        wins = rounds = 0
        fan_sum = wins_fan = baotou = dealer_rounds = dealer_wins = score_sum = 0
        for room, recs in blk["rooms"].items():
            rw = sum(1 for r in recs if r["win"])
            wins += rw
            rounds += len(recs)
            per_room.append(rw / float(len(recs)))
            # 同房差分（配对估计量）：需要该房的对手胡数/轮数；缺这房的对手数据时跳过
            _n = len(recs)
            _ow, _on = blk.get("opp_by_room", {}).get(room, (0, 0))
            if _n and _on:
                _d = rw / float(_n) - _ow / float(_on)
                per_room_diff.append(_d)
            for r in recs:
                score_sum += r["score"]
                if r["dealer"]:
                    dealer_rounds += 1
                    dealer_wins += 1 if r["win"] else 0
                if r["win"]:
                    fan_sum += r["fan"]
                    wins_fan += 1
                    baotou += 1 if r["baotou"] else 0
        p = wins / float(rounds) if rounds else 0.0
        se_binom = math.sqrt(p * (1 - p) / rounds) if rounds else 0.0
        if len(per_room) > 1:
            m = sum(per_room) / len(per_room)
            var = sum((x - m) ** 2 for x in per_room) / (len(per_room) - 1)
            se_cluster = math.sqrt(var / len(per_room))
        else:
            m, se_cluster = (per_room[0] if per_room else 0.0), 0.0
        diff_mean = se_diff = 0.0
        if len(per_room_diff) > 1:
            diff_mean = sum(per_room_diff) / len(per_room_diff)
            _var = sum((x - diff_mean) ** 2 for x in per_room_diff) / (len(per_room_diff) - 1)
            se_diff = math.sqrt(_var / len(per_room_diff))
        res[arm] = dict(rooms=len(per_room), rounds=rounds, wins=wins, win=p,
                        se_binom=se_binom, se_cluster=se_cluster,
                        diff=diff_mean, se_diff=se_diff, n_diff=len(per_room_diff),
                        room_win_mean=m, fan_per_win=(fan_sum / wins_fan if wins_fan else 0.0),
                        baotou_rate=(baotou / wins_fan if wins_fan else 0.0),
                        dealer_win=(dealer_wins / dealer_rounds if dealer_rounds else 0.0),
                        score_per_round=(score_sum / rounds if rounds else 0.0),
                        per_room=per_room)
    return res


def compare(a, b):
    """两臂胜率差（b − a）：返回 dict{diff, se, z, se_used, note}。取更保守的 SE。"""
    p1, n1 = a["win"], a["rounds"]
    p2, n2 = b["win"], b["rounds"]
    se_b = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) if n1 and n2 else 0.0
    se_c = math.sqrt(a["se_cluster"] ** 2 + b["se_cluster"] ** 2)
    se = max(se_b, se_c)
    diff = p2 - p1
    return dict(diff=diff, se=se, z=(diff / se if se else 0.0), se_binom=se_b, se_cluster=se_c,
                note=("cluster" if se_c >= se_b else "binom"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="", help="逗号分隔；缺省取当前战役两臂")
    ap.add_argument("--since", default="", help="只统计该时间戳之后的房（与 ab_readout 的 started 同口径）")
    ap.add_argument("--dirs", default="server,recent")
    ap.add_argument("--verbose", action="store_true", help="打印房级胜率明细")
    a = ap.parse_args(argv)

    arms, started = campaign()
    if a.arms.strip():
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if not arms:
        raise SystemExit("无臂可看（--arms 或先启动 A/B）")
    since = a.since or started
    data = collect(arms, since=since, dirs=[x.strip() for x in a.dirs.split(",") if x.strip()])
    st = summarize(data)

    print("=" * 78)
    print("A/B 胜率读数（口径 = 只能自摸，与排行榜一致）")
    print("  窗口 since=%s   数据 = var/replays/%s" % (since or "-", a.dirs))
    print("-" * 78)
    print("%-14s %5s %7s %7s %8s %8s %8s %8s %7s" %
          ("arm", "房", "局", "胡", "胜率", "SE二项", "SE聚类", "均番/胡", "爆头%"))
    for arm in arms:
        s = st[arm]
        print("%-14s %5d %7d %7d %7.2f%% %7.2f%% %7.2f%% %8.2f %7.1f%%" %
              (arm, s["rooms"], s["rounds"], s["wins"], 100 * s["win"],
               100 * s["se_binom"], 100 * s["se_cluster"], s["fan_per_win"],
               100 * s["baotou_rate"]))
    if len(arms) == 2:
        A, B = st[arms[0]], st[arms[1]]
        c = compare(A, B)
        dpp = 100.0 * c["diff"]
        cipp = 1.96 * c["se"] * 100.0
        print("-" * 78)
        print("  b − a = %+.2fpp  ±%.2fpp（95%%，取更保守的 %s SE）  z=%+.2f"
              % (dpp, cipp, c["note"], c["z"]))
        print("  两个 SE：二项 %.2fpp / 房级聚类 %.2fpp（房内 80 局不独立 ⇒ 取大者）"
              % (100 * c["se_binom"], 100 * c["se_cluster"]))
        print("  换算成排行榜口径（+0.01 胜率 ≈ +28 原始分/房）⇒ 本读数 ≈ **%+.1f 分/房**"
              % (2800.0 * c["diff"]))
        # ★ 功率必须用**方差膨胀后的** SE（房内相关），否则会严重低估所需样本。
        #   实测：每房 80 轮、房级 SD 6.5pp ⇒ 二项 SE 0.28pp 但聚类 SE 0.38pp（膨胀 1.35×）。
        p_pool = (A["wins"] + B["wins"]) / float(A["rounds"] + B["rounds"]) if (A["rounds"] + B["rounds"]) else 0.0
        des = 1.0
        if A["se_binom"] > 0:
            des = (c["se_cluster"] / c["se_binom"]) ** 2 if c["se_binom"] > 0 else 1.0
        # 单臂所需**轮数**（两级 SE：房级 SD 与二项之比 = 设计效应）
        if abs(c["diff"]) > 0 and p_pool > 0:
            se1 = math.sqrt(p_pool * (1 - p_pool) / 1.0) * math.sqrt(max(des, 1.0))
            n_rounds = 2 * (1.96 * se1 / abs(c["diff"])) ** 2
            print("  方差膨胀（房内相关）：设计效应 ≈ **%.2f×**（聚类 SE %.2fpp / 二项 SE %.2fpp）"
                  % (des, 100 * c["se_cluster"], 100 * c["se_binom"]))
            print("  功率（含膨胀）：想判出这个效应需任意臂 ~%.0f 轮 ≈ %.0f 房（每房 80 轮）"
                  % (n_rounds, n_rounds / 80.0))
            print("  ⚠ 只看『按局二项』会低估样本（%.0fx）；本工具比较与功率都用保守口径。"
                  % max(des, 1.0))
        # ★ 同房配对差分：Arm 自身胜率 − 同房三对手合并胜率（对手吸收房间难度）
        print("-" * 78)
        print("  同房配对差分（我方胜率 − 同房三对手合并胜率，按房配对）:")
        for arm in arms:
            _s = st[arm]
            print("    %-14s %+6.2fpp  ±%.2fpp（95%%，n=%d 房）  z=%+.2f"
                  % (arm, 100 * _s["diff"], 1.96 * 100 * _s["se_diff"], _s["n_diff"],
                     (_s["diff"] / _s["se_diff"]) if _s["se_diff"] else 0.0))
        if st[arms[0]]["se_diff"] and st[arms[1]]["se_diff"]:
            _dd = st[arms[1]]["diff"] - st[arms[0]]["diff"]
            _ss = math.sqrt(st[arms[0]]["se_diff"] ** 2 + st[arms[1]]["se_diff"] ** 2)
            print("    差分差（%s − %s）= %+.2fpp  ±%.2fpp  z=%+.2f"
                  % (arms[1], arms[0], 100 * _dd, 1.96 * 100 * _ss, _dd / _ss))
            print("    ⚠ 这不是更敏感的判据：d=(4p−1)/3 是 p 的线性变换（SD 7.25pp vs 6.53pp），用它判效应需要更多房。")
            print("       它的用途是**零假设标尺**（对手在同批房里的表现）与展示；判据仍用原始胜率/净胜/房。")
        print("  ⚠ 采用判据仍以 ab_readout（净胜/房）为准；本表用于**独立复核 + 提前看机制方向**。")
    if a.verbose:
        for arm in arms:
            print("\n[%s] 房级胜率（%%）" % arm)
            for room, recs in data[arm]["rooms"].items():
                w = sum(1 for r in recs if r["win"])
                print("  %-24s %3d局 %5.1f%%" % (room, len(recs), 100.0 * w / len(recs)))
    print("=" * 78)


if __name__ == "__main__":
    main()
