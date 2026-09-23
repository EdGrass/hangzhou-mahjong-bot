# -*- coding: utf-8 -*-
"""提前采用 A/B 的较优臂（**预登记中期规则**，操作单 §26.5）。

为什么要有它：若候选真的好，等到攒够房数（40h+）才采用 = 白丢几十小时的收益
（每房 100 分 × 剩余小时 × 4 房/h）。代价是提前看会抬假阳性，故要求
    **|t| ≥ 3.00 且两侧各 ≥12 房**（单次 α≈0.3%），且驱动自带的双档熔断仍然生效。

本脚本做三件事（安全顺序）：
  1) 复核当前战役臂与阈值（不够就拒绝，除非 --force）；
  2) `tools/ab_ctl.py stop` —— 它会让驱动自行退出并**写回基线**（绝不中途杀 run_bot）；
  3) 把选定臂写进 `var/_keeper_strategy.txt`，watchdog ≤90s 用该策略恢复 keeper；
     并把决策证据落到 `var/_ab_adopt_log.jsonl`（可复核）。

用法：
    python -X utf8 tools/ab_adopt.py speedc132 --dry-run
    python -X utf8 tools/ab_adopt.py speedc132
"""
from __future__ import annotations
import argparse, io, json, math, os, statistics, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ME = "u_7a3fba48d70b"
AB = os.path.join(ROOT, "var", ".ab_mode")
STRAT_FILE = os.path.join(ROOT, "var", "_keeper_strategy.txt")
LOG = os.path.join(ROOT, "var", "_ab_adopt_log.jsonl")
T_THRESHOLD = 3.0          # 预登记**中期**规则：|t|>=3 且各 >=12 房 ⇒ 立即采用
MIN_ROOMS = 12
BUNDLE_THRESHOLD = 1.50    # 预登记**战役终点**规则（组合臂）：点估计为正且 t>=1.5
BUNDLE_ROOMS = 150
SINGLE_THRESHOLD = 1.96    # 预登记**战役终点**规则（单变量）
SINGLE_ROOMS = 100
# ★ 2026-09-21（R884）：预登记 §2.2 的“临时采用”与 §2.2-bis 的“非劣性”两档
#   **原文早已写死**，但本工具此前**只实现了 mid/end 两档** ⇒ 那两档判词出不来
#   （只能 --force，丢掉 rule 审计语义）。现补齐；**默认不生效**，需显式开关。
PROVISIONAL_T = 1.28       # §2.2 临时采用：t >= 1.28 且 >=100 房/臂（下一役强制复核）
NONINF_T = -1.28           # §2.2-bis 机制候选：t > -1.28 且 >=100 房/臂
REDUCED_ROOMS = 100


def _campaign():
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return [], None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    return [str(x) for x in (arms or []) if x], cfg.get("started")


def verdict(t, na, nb, is_bundle):
    """预登记判据（纯函数，可单测）：返回 (ok, rule)。

    中期规则：|t|>=3.0 且各臂 >=12 房 ⇒ 立即采用（rule="mid"）
    终点规则：样本够 + t 达阈值 ⇒ 采用（rule="end"）；组合臂 1.50/150 房，单变量 1.96/100 房
    """
    nmin = min(na, nb)
    if abs(t) >= T_THRESHOLD and nmin >= MIN_ROOMS:
        return True, "mid"
    thr = BUNDLE_THRESHOLD if is_bundle else SINGLE_THRESHOLD
    n_end = BUNDLE_ROOMS if is_bundle else SINGLE_ROOMS
    if nmin >= n_end and t >= thr:
        return True, "end"
    return False, None


def _bundles():
    """当前战役里被**预先声明为组合臂**的策略名（.ab_mode 的 bundles；缺省空）。"""
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return set()
    return set(str(x) for x in (cfg.get("bundles") or []))


def _campaign_rooms(since):
    """本战役**轮转批次**归属的 {room: arm}（与 `ab_readout.arm_rooms_from_log` 同一口径）。

    2026-09-20（R670）：`_rooms()` 原先按**策略名**归属，会把"A/B 开始前旧批次还在跑的基线房"
    算进本役 —— 实测本役开局就有 **3 房尾单**被算成基线（`ab_adopt` 报 speedtugc=4，而
    `ab_readout` 报 1，两者不一致）。这正是 `arm_rooms_from_log` 注释里明确警告要避免的错误：
    "A/B 开始前旧批次跑的可能就是基线策略 ⇒ 会被错误算成臂 a"。
    **采用判据必须与读数口径一致**，故这里改以排批日志为准。

    取不到日志（单测夹具/冷启动/老战役）⇒ 返回 None ⇒ 调用方**自动退化为原口径**。
    """
    lp = os.path.join(ROOT, "var", "_ab_log.jsonl")
    if not os.path.exists(lp):
        # 单测夹具 / 冷启动 / 旧战役：没有排批日志 ⇒ 退化为按策略名归属（老口径）
        return None
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from ab_readout import arm_rooms_from_log          # 只读、无副作用
        m = arm_rooms_from_log(since, log_path=lp) or {}
        out = {}
        for arm, rs in m.items():
            for r in (rs or []):
                room = r.get("room")
                if room:
                    out[room] = arm
        return out or None
    except Exception:
        return None


def _rooms(roommap=None):
    """按 auto_ranking 的 room→strategy 归属取房；**有 roommap 时以排批日志为准**（R670）。"""
    out = {}
    for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        rk = d.get("ranking") or []
        mine = next((x for x in rk if x.get("user_id") == ME), None)
        oth = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME]
        if mine is None or len(oth) != 3:
            continue
        _st = d.get("strategy") or "?"
        if roommap is not None and roommap.get(d.get("room")) != _st:
            continue                    # 不属于本役轮转批次（如 A/B 开始前旧批次的尾单）
        out.setdefault(_st, []).append(
            {"ts": d.get("ts") or "", "room": d.get("room") or "",
             "first": (max(rk, key=lambda x: x.get("total_score") or 0).get("user_id") == ME),
             "net": (mine.get("total_score") or 0) - sum(oth) / 3.0})
    return out


def _stats(arm, allr, started):
    rs = [r for r in allr.get(arm, []) if (not started or r["ts"] >= started)]
    n = len(rs)
    if n == 0:
        return n, 0.0, 0.0
    nets = [r["net"] for r in rs]
    return n, statistics.mean(nets), (statistics.pstdev(nets) / math.sqrt(n) if n > 1 else 0.0)


def _first_rate(arm, allr, started):
    """该臂在战役窗口内的**第一率**（用户裁定的唯一 score-side 口径，R522）。

    2026-09-20 补：预登记 §6 写的是"采用还需**分/房为正 且 第一率不低于基线**"，
    但本工具的判据此前只看净胜/房 ⇒ **预登记规则没有被工具实现**。此处补上。
    """
    rs = [r for r in allr.get(arm, []) if (not started or r["ts"] >= started)]
    n = len(rs)
    if not n:
        return 0, 0.0
    return n, sum(1 for r in rs if r.get("first")) / float(n)


def adopt_ok(t, t_adj, first_cand, first_base, nmin, is_bundle, mode=None):
    """**采用判据（纯函数，三道护栏齐全）** —— R690 抽出，便于单测钉住。

    返回 (ok, rule)。三道判据（全部必须过）：
      ① 原始 t ≥ 阈值（中期 3.00 且各 ≥12 房；终点 单变量 1.96/100 房、组合臂 1.50/150 房）；
      ② **桌强调整后 t ≥ 0**（防止"房更容易"被读成"臂更强"，R658）；
      ③ **候选第一率 ≥ 基线第一率**（用户裁定的 score-side 口径，预登记 §6，R663）。
    """
    ok_mid = (t >= T_THRESHOLD) and (nmin >= MIN_ROOMS) and (t_adj >= 0.0) and (first_cand >= first_base)
    if ok_mid:
        return True, "mid"
    thr = BUNDLE_THRESHOLD if is_bundle else SINGLE_THRESHOLD
    n_end = BUNDLE_ROOMS if is_bundle else SINGLE_ROOMS
    ok_end = (nmin >= n_end) and (t >= thr) and (t_adj >= 0.0) and (first_cand >= first_base)
    if ok_end:
        return True, "end"
    # ★ R884：两档**降低门槛**的预登记规则（仅在显式指定 mode 时生效）：
    #   §2.2   临时采用  →  t>=1.28 且 >=100 房/臂；
    #   §2.2-bis 非劣性  →  t>-1.28 且 >=100 房/臂。
    #   ⚠ 两档都**保留第三道护栏**（候选第一率不低于基线）——
    #     第一率是用户裁定的主口径（§6）；而第二道护栏（桌强调整后 t>=0）
    #     在这两档里**不作阻塞**（预登记原文未要求），但 CLI 会显式提示。
    if mode == "provisional":
        if nmin >= REDUCED_ROOMS and t >= PROVISIONAL_T and first_cand >= first_base:
            return True, "provisional"
    elif mode == "noninf":
        if nmin >= REDUCED_ROOMS and t > NONINF_T and first_cand >= first_base:
            return True, "noninf"
    return False, None


def _strength_ctx():
    """返回 (room→LOO对手强度, beta)。

    2026-09-20（R653）：**房强是本作最大的单一协变量** —— 每 +1 强度 ⇒ 我方约 −0.6~−1.2 分/房，
    而臂间房强差异可达 ±20 分/房 ⇒ 不校正时会把"房更容易"读成"臂更强"。β 用全量 finished 房现算。
    取不到则返回 ({}, 0.0)，下游自动退化为原始口径（不影响老测试与冷启动）。
    """
    try:
        from opp_strength import load_rows, opponent_strength, slope
    except Exception:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from opp_strength import load_rows, opponent_strength, slope
        except Exception:
            return {}, 0.0
    try:
        rows = load_rows(os.path.join(ROOT, "var", "auto_ranking.jsonl"))
        ostr = opponent_strength(rows)
        pts = []
        for d in rows:
            if d.get("status") != "finished":
                continue
            o = ostr.get(d.get("room"))
            mine = next((x for x in (d.get("ranking") or []) if x.get("user_id") == ME), None)
            if o is None or mine is None:
                continue
            oth = [x.get("total_score") or 0 for x in (d.get("ranking") or []) if x.get("user_id") != ME]
            if len(oth) != 3:
                continue
            pts.append((o, (mine.get("total_score") or 0) - sum(oth) / 3.0))
        beta = slope([a for a, _ in pts], [b for _, b in pts]) if len(pts) >= 10 else 0.0
        return ostr, float(beta or 0.0)
    except Exception:
        return {}, 0.0


def _adj_stats(arm, allr, started, ostr, beta):
    """桌强调整后的 (n, mean, se)。强度缺失的房按 beta=0 处理（= 原始值）。"""
    rs = [r for r in allr.get(arm, []) if (not started or r["ts"] >= started)]
    adj = []
    for r in rs:
        o = ostr.get(r.get("room"))
        adj.append(r["net"] - (beta * o if o is not None else 0.0))
    n = len(adj)
    if n == 0:
        return 0, 0.0, 0.0
    return n, statistics.mean(adj), (statistics.pstdev(adj) / math.sqrt(n) if n > 1 else 0.0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="跳过阈值检查（仍会记录理由）")
    _g = ap.add_mutually_exclusive_group()
    _g.add_argument("--provisional", action="store_true",
                    help="启用预登记 §2.2 临时采用档：t>=1.28 且 >=100 房/臂")
    _g.add_argument("--noninf", action="store_true",
                    help="启用预登记 §2.2-bis 非劣性档：t>-1.28 且 >=100 房/臂（机制前提候选）")
    a = ap.parse_args(argv)
    arms, started = _campaign()
    if not arms:
        print("FAIL 无 var/.ab_mode（A/B 未在跑）—— 若只想换生产策略，请用 "
              "python -X utf8 var/_switch_test_strategy.py <strategy>"); return 2
    if a.arm not in arms:
        print("FAIL %r 不在当前战役臂 %s 内" % (a.arm, arms)); return 2
    reg = io.open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8").read()
    if ('"%s"' % a.arm) not in reg:
        print("FAIL %r 未注册到 run_bot.py 的 STRATEGY_FACTORIES" % a.arm); return 2
    allr = _rooms(_campaign_rooms(started))
    st = {}
    for x in arms:
        st[x] = _stats(x, allr, started)
    base = arms[0]
    na, ma, sa = st[base]
    nb, mb, sb = st[a.arm]
    se = math.sqrt(sa * sa + sb * sb)
    t = (mb - ma) / se if se else 0.0
    # ★ 2026-09-20（R653）：桌强调整后 t。房强是本作最大协变量（±20 分/房量级）
    #   而臂间房强差可达同量级 ⇒ 不校正会把'房更容易'读成'臂更强'。取不到强度 ⇒ adj 退化为 raw。
    _ostr, _beta = _strength_ctx()
    adja = _adj_stats(base, allr, started, _ostr, _beta)
    adjb = _adj_stats(a.arm, allr, started, _ostr, _beta)
    _se_adj = math.sqrt(adja[2] ** 2 + adjb[2] ** 2)
    t_adj = ((adjb[1] - adja[1]) / _se_adj) if _se_adj else t
    _fa = _first_rate(base, allr, started)
    _fb = _first_rate(a.arm, allr, started)
    _fr_ok = (_fb[1] >= _fa[1])
    # ★ 多臂修正：对**被请求的臂**与基线比较；当前较优按所有候选臂的平均净胜选最大。
    candidates = arms[1:]
    # 只用达到中期最小房数的候选参与“当前较优”选择，避免 0~1 房高均值假阻塞。
    eligible = [x for x in candidates if st[x][0] >= MIN_ROOMS]
    if not eligible:
        eligible = [x for x in candidates if st[x][0] > 0]
    best_cand = max(eligible, key=lambda x: st[x][1]) if eligible else base
    win = best_cand if st[best_cand][1] > ma else base
    print("当前战役 %s（started=%s；本次比较 %s vs %s）" % (" vs ".join(arms), started, a.arm, base))
    for x in arms:
        n, m, s = st[x]
        _an, _am, _as = _adj_stats(x, allr, started, _ostr, _beta)
        _fn, _fv = _first_rate(x, allr, started)
        print("  %-14s 房=%3d  净胜/房 %+8.1f ±%5.1f   桌强调整后 %+8.1f ±%5.1f   **第一率 %5.1f%%**" % (x, n, m, 1.96 * s, _am, 1.96 * _as, 100.0 * _fv))
    bundles = _bundles()
    is_bundle = a.arm in bundles
    thr_end = BUNDLE_THRESHOLD if is_bundle else SINGLE_THRESHOLD
    n_end = BUNDLE_ROOMS if is_bundle else SINGLE_ROOMS
    tag = "组合臂" if is_bundle else "单变量"
    nmin = min(na, nb)
    # 采用必须是“相对基线为正”的效应；中期也不采用反向显著臂。
    # ★ 三道护栏集中在纯函数 adopt_ok 里（R691）⇒ 单测可直接钉住，且**显示与实际判据同源**。
    _mode = "provisional" if a.provisional else ("noninf" if a.noninf else None)
    _ok, _rule = adopt_ok(t, t_adj, _fb[1], _fa[1], nmin, is_bundle, mode=_mode)
    ok_mid = (_rule == "mid")
    ok_end = (_rule == "end")
    ok_prov = (_rule == "provisional")
    ok_noninf = (_rule == "noninf")
    print("  %s−%s t=%.2f（桌强调整后 t=%.2f，β=%+.2f）  当前较优臂=%s  臂类型=%s" % (a.arm, base, t, t_adj, _beta, win, tag))
    print("  第一率：%s %.1f%%（%d 房） vs %s %.1f%%（%d 房）  ⇒ 预登记护栏（候选须不低于基线）[%s]" % (a.arm, 100.0 * _fb[1], _fb[0], base, 100.0 * _fa[1], _fa[0], "通过" if _fr_ok else "未过"))
    if not _fr_ok:
        print("  ⚠ **第一率低于基线**：预登记 §6 要求『分/房为正 且 第一率不低于基线』⇒ 不采用（要强行请 --force）")
    if t >= thr_end and t_adj < 0.0:
        print("  ⚠ 原始 t 达标但**桌强调整后 t<0** ⇒ 该效应可能是'房更容易'而非'臂更强' ⇒ 按预登记护栏不采用")
    print("  判据：中期 t≥%.2f 且各≥%d 房  [%s]；终点 %s t≥%.2f 且各≥%d 房  [%s]"
          % (T_THRESHOLD, MIN_ROOMS, "通过" if ok_mid else "未过",
             tag, thr_end, n_end, "通过" if ok_end else "未过"))
    if _mode:
        _rt = PROVISIONAL_T if _mode == "provisional" else NONINF_T
        _sym = ">=" if _mode == "provisional" else ">"
        print("  判据（%s）：t %s %.2f 且各>=%d 房  [%s]；⚠ 桌强调整后 t=%.2f（该档**不**作阻塞，仅提示）"
              % (_mode, _sym, _rt, REDUCED_ROOMS,
                 "通过" if (ok_prov or ok_noninf) else "未过", t_adj))
    ok = ok_mid or ok_end or ok_prov or ok_noninf
    if not ok and not a.force:
        print("REFUSE 预登记判据都未达（含所选档 %s）⇒ 继续攒房（要强行采用请加 --force，会在日志里记录）" % (_mode or "中期/冻结"))
        return 3
    if a.arm != win and not a.force:
        print("REFUSE %r 不是当前较优臂（%r）" % (a.arm, win)); return 3
    ev = {"ts_utc": None, "arms": arms, "started": started, "chosen": a.arm, "baseline": base,
          "win_by_mean": win, "t": round(t, 3), "t_adj": round(float(t_adj), 3), "beta": round(float(_beta), 3),
          "first_rate": {k: round(_first_rate(k, allr, started)[1], 4) for k in arms}, "rooms": {k: st[k][0] for k in arms},
          "mean_net": {k: round(st[k][1], 2) for k in arms},
          "forced": bool(a.force), "threshold_met": bool(ok), "rule": (_rule or "forced"), "is_bundle": bool(is_bundle), "bundle_threshold": thr_end, "end_rooms": n_end,
          "t_threshold": T_THRESHOLD, "min_rooms": MIN_ROOMS}
    if a.dry_run:
        print("[dry-run] 将执行：ab_ctl.py stop → 写入 var/_keeper_strategy.txt=%s → 记 %s" % (a.arm, LOG))
        print("[dry-run] 证据：%s" % json.dumps(ev, ensure_ascii=False))
        return 0
    print("1) 停 A/B（驱动会自行退出并写回基线，不杀在途对局）…")
    rc = subprocess.call([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "ab_ctl.py"), "stop"])
    if rc != 0:
        print("FAIL ab_ctl stop 退出码 %s" % rc); return 4
    io.open(STRAT_FILE, "w", encoding="utf-8").write(a.arm)
    cur = io.open(STRAT_FILE, encoding="utf-8").read().strip()
    if cur != a.arm:
        print("FAIL 策略文件写入失败：%r" % cur); return 5
    import datetime
    ev["ts_utc"] = datetime.datetime.now().isoformat(timespec="seconds")
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print("2) 已把生产策略写为 %s，并记录到 %s" % (a.arm, os.path.basename(LOG)))
    print("3) watchdog 将在 ≤90s 内用该策略恢复 keeper；用 python -X utf8 var/_daily.py 复核")
    return 0


if __name__ == "__main__":
    sys.exit(main())
