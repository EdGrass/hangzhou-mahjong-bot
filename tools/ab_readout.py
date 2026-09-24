# -*- coding: utf-8 -*-
"""并发交替 A/B 的读数：按臂给出 净胜/房 ±95%、正分率、均名次，并给判定。

为什么看「净胜/房」：= 我方总分 − 同房另三家均分。它把「这一房有多难」扣掉，
配合交替排批（两臂同池同时段），是本项目唯一被证明可信的判据（见 field-audit §21）。
"""
from __future__ import annotations
import io
import json
import math
import os
import datetime
import glob
import statistics
import sys

# ★ 桌强（2026-09-16）：既支持 `import ab_readout`（tools/ 在 path 上），也支持
#   以**文件路径**加载（tests/test_ab_mode.py 用 importlib；那时 tools/ 不在 sys.path 上）。
try:
    from opp_strength import load_rows, opponent_strength, slope
except ImportError:                                          # pragma: no cover
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "opp_strength", os.path.join(os.path.dirname(os.path.abspath(__file__)), "opp_strength.py"))
    _m = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
    load_rows, opponent_strength, slope = _m.load_rows, _m.opponent_strength, _m.slope

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLAYS = os.path.join(ROOT, "var", "replays")
OVERHEAD_MIN = 0.7   # 房与房之间的排批开销（实测 23s~1.5min，取 0.7min；原设 3min 会把净胜/小时低估约 15%）


def room_starts():
    """room_id -> 开打时刻（从 var/replays/auto_<ts>/ 目录名与其内文件名解析）。
    用于给出**每臂的房时长** —— A/B 判据必须包含吞吐代价（房越长 = 单位时间房数越少）。"""
    m = {}
    for d in glob.glob(os.path.join(REPLAYS, "auto_*")):
        n = os.path.basename(d)
        if len(n) < 19:
            continue
        try:
            st = datetime.datetime.strptime(n[:19], "auto_%Y%m%d_%H%M%S")
        except Exception:
            continue
        fs = glob.glob(os.path.join(d, "*.jsonl"))
        if not fs:
            continue
        rid = os.path.basename(fs[0]).split("_r")[0]
        m[rid] = st
    return m
ME = "u_7a3fba48d70b"
RANKING = os.path.join(ROOT, "var", "auto_ranking.jsonl")


def _norm_since(since):
    """Normalize a --since boundary to the ledger's ts format (SPACE separator).

    auto_ranking.jsonl writes ts as "YYYY-MM-DD HH:MM:SS". A boundary written in
    ISO form ("YYYY-MM-DDTHH:MM:SS") compares as GREATER than every row of that
    day because " " < "T", so all rooms of that date are SILENTLY dropped.
    Observed 2026-09-21: --since 2026-09-20T14:54:07 reported 30/29 rooms while
    --since "2026-09-20 14:54:07" reported the true 46/46 (t 1.52 vs 1.38).
    """
    if not since:
        return None
    return since.strip().replace("T", " ")


def _ts_ge(ts, since):
    return (not since) or (ts or "") >= since

VALID_GAMES = 80          # 自动房固定 80 局/房（见 STATUS §10）
INVALID = {}              # (ts, room) -> 原因；主流程末尾提示排除了几房


_CONFLICT_CACHE = {}


def _conflict_rooms():
    """★ 2026-09-16 新增：同房出现**多个策略** ⇒ 该房两臂都不算。

    事故链（实测 19:23）：候选臂的 run_bot 被一次离线重放 OOM 杀掉 ⇒ 该房以
    `status=running` 落盘；驱动排下一批（基线臂）时 `/api/match` **幂等返回同一个房**
    （平台"绝不双房双席"）⇒ 这**一房的前 23 手是候选臂打的、其余是基线臂打的**。
    按房 id 排掉它，比"按行排"更保守（门户读数同样会报这个冲突）。
    """
    key = RANKING
    if key in _CONFLICT_CACHE:
        return _CONFLICT_CACHE[key]
    seen = {}
    try:
        for ln in io.open(RANKING, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            r, st = d.get("room"), d.get("strategy")
            if r and st:
                seen.setdefault(r, set()).add(st)
    except OSError:
        seen = {}
    out = set(r for r, ss in seen.items() if len(ss) > 1)
    _CONFLICT_CACHE[key] = out
    return out


def _invalid_reason(d):
    """★ 2026-09-16 新增：排除**非完成房**（半房快照会同时污染计数与均值）。

    事故实测：19:23:18 一次离线重放 OOM 杀掉了 c151 的 run_bot，该房以
    `status=running / exit_code=4294967295 / games_played=23` 落盘 —— 那是半房快照，
    不是 80 局结果；旧口径会把它当成一个"真实的 c151 房"。
    """
    # 缺字段 = 兼容旧记录/测试夹具，**不算无效**；只排除能明确判定的坏记录
    st = d.get("status")
    if st is not None and st != "finished":
        return "status=%s" % st
    ec = d.get("exit_code")
    if ec is not None and ec != 0:
        return "exit=%s" % ec
    mine = next((x for x in (d.get("ranking") or []) if x.get("user_id") == ME), None)
    gp = (mine or {}).get("games_played")
    if gp is not None and gp != VALID_GAMES:
        return "games=%s" % gp
    if d.get("room") in _conflict_rooms():
        return "multi-strategy"
    return None
AB = os.path.join(ROOT, "var", ".ab_mode")


def _current_campaign():
    """读 var/.ab_mode → (当前臂列表, 起始时间)。缺失/异常 → (None, None)。"""
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return None, None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    arms = [str(x) for x in (arms or []) if x]
    return (arms or None), cfg.get("started")


def rooms_for(strategy, since=None):
    since = _norm_since(since)
    out = []
    try:
        for ln in io.open(RANKING, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("strategy") != strategy:
                continue
            if not _ts_ge(d.get("ts", ""), since):
                continue
            _why = _invalid_reason(d)
            if _why:
                INVALID[(d.get("ts"), d.get("room"))] = _why
                continue
            rk = d.get("ranking") or []
            mine = next((x for x in rk if x.get("user_id") == ME), None)
            others = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME]
            if mine is None or len(others) != 3:
                continue
            out.append({"net": (mine.get("total_score") or 0) - sum(others) / 3.0,
                        "score": mine.get("total_score") or 0,
                        "rank": mine.get("rank") or 0,
                        "room": d.get("room"),
                        "ts": d.get("ts")})
    except OSError:
        pass
    return out


def arm_rooms_from_log(since, log_path=None):
    """按驱动排批日志把房间**精确归属**到臂。

    为什么不能按「策略名」归属：A/B 开始前旧批次跑的可能就是基线策略
    （实测：19:49 开 A/B，旧批次 19:54/20:07/20:21 三房也是 speedtugc，
    会被错误算成臂 a）。这里用 `_ab_log.jsonl` 的排批时刻做窗口：
    某臂的一次排批 → 取 `ts >= 排批时刻` 的**第一条同策略完成记录**。
    """
    since = _norm_since(since)
    launches = []
    lp = log_path or os.path.join(ROOT, "var", "_ab_log.jsonl")
    if os.path.exists(lp):
        for ln in io.open(lp, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if not d.get("arm") or not d.get("strategy"):
                continue          # 跳过旧格式（_keeper_ab 时代）
            if not _ts_ge(d.get("ts", ""), since):
                continue
            launches.append((d["ts"], d["arm"], d["strategy"]))
    launches.sort()
    done = []
    if os.path.exists(RANKING):
        for ln in io.open(RANKING, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            rk = d.get("ranking") or []
            if not any(x.get("user_id") == ME for x in rk):
                continue
            _why = _invalid_reason(d)
            if _why:
                INVALID[(d.get("ts"), d.get("room"))] = _why
                continue
            done.append((d.get("ts", ""), d.get("strategy"), d))
    done.sort(key=lambda x: x[0])
    used = set()
    out = {}
    for ts, arm, strat in launches:
        for i, (dts, dst, d) in enumerate(done):
            if i in used or dst != strat or dts < ts:
                continue
            used.add(i)
            out.setdefault(strat, []).append(d)      # 按**策略名**聚合，兼容 a/b 与 arms 两种配置
            break
    return out


# 预登记阈值（**必须与 tools/ab_adopt.py 一致**；tests/test_ab_readout_multi.py 有跨工具一致性断言）
T_THRESHOLD = 3.0
MIN_ROOMS = 12
BUNDLE_THRESHOLD = 1.50
BUNDLE_ROOMS = 150
SINGLE_THRESHOLD = 1.96
SINGLE_ROOMS = 100
FUTILITY_T = 0.60       # 预登记「无效性提前收尾」：样本已够但效应太小 ⇒ 判 null
FUTILITY_ROOMS = 100


def room_rank_stats(strategy, since=None):
    """★ 房间级"第一名率"（first%）—— 2026-09-16 新增（见 STATUS §4c-39）。

    为什么看它：四人房里**随机也能拿 25% 第一**，而我方历史只有 **18.2%**、榜首 42~55%；
    且第一名房间的平均原始分 +200（第二名只有 +48）⇒ 房间级收益被"能不能拿第一"主导。
    它比"净值"更宽口径、且与门户 `me.firsts/me.rooms` 同源，适合当**机制是否在起作用的辅助指标**。
    ⚠ 房间级统计噪声极大：12-20 房只能看方向，下结论仍需 §4c-29 的房数量级。
    """
    ranks = [r["rank"] for r in rooms_for(strategy, since) if r.get("rank")]
    n = len(ranks)
    if not n:
        return None
    return {"rooms": n, "firsts": sum(1 for x in ranks if x == 1), "first_pct": 100.0 * sum(1 for x in ranks if x == 1) / n}


def arm_verdict(t, na, nb, is_bundle):
    """两臂/多臂共用的预登记判据（纯函数）：返回 (verdict, threshold, end_n)。

    verdict ∈ {adopt-early, adopt, keep-baseline, futility, pending}；
    与 ab_adopt.verdict 同源同值（futility 是 readout 独有的收尾建议，不影响 adopt 是否采用）。

    无效性提前收尾（2026-09-17 预登记）：各 >=FUTILITY_ROOMS(=100) 房且 |t| < FUTILITY_T(=0.6)
    ⇒ 判 null。理由：|t| 只随 sqrt(n) 增长，再跑到 150 房/臂期望 |t| 也只有原值的 1.2247 倍
    （100→150 房），即 <0.74，基本不可能摸到组合臂阈值 1.50；继续跑只是白交实验税。
    """
    thr = BUNDLE_THRESHOLD if is_bundle else SINGLE_THRESHOLD
    end_n = BUNDLE_ROOMS if is_bundle else SINGLE_ROOMS
    nmin = min(int(na), int(nb))
    if abs(t) >= T_THRESHOLD and nmin >= MIN_ROOMS and t > 0:
        return "adopt-early", thr, end_n
    if t <= -T_THRESHOLD and nmin >= MIN_ROOMS:
        return "drop-arm", thr, end_n
    if nmin >= FUTILITY_ROOMS and abs(t) < FUTILITY_T:
        return "futility", thr, end_n
    if nmin >= end_n:
        return ("adopt" if t >= thr else "keep-baseline"), thr, end_n
    return "pending", thr, end_n


def multi_arm_report(arms, cur_arms, cur_started, bundles, out=print):
    """多臂战役：**逐个候选臂 vs 基线**（返回每臂结果 dict，便于测试/自动化）。

    arms: {strategy: [room_dict, ...]}（room_dict 至少含 "net" / "ts"）
    bundles: 预先声明为「组合臂」的策略名集合（阈值 1.50；单变量 1.96）
    判据（预登记）：中期 |t|≥3.0 且各 ≥12 房 ⇒ 立即采用；战役结束（各 ≥90 房）⇒
    t ≥ 阈值 则采用、否则维持基线。
    """
    res = []
    try:
        _cur = list(cur_arms or [])
        if len(_cur) < 3 or not all(x in arms for x in _cur):
            return res
        base = _cur[0]
        A = [r for r in arms[base] if (not cur_started or r.get("ts", "") >= cur_started)]
        if len(A) < 2:
            return res
        ma = statistics.mean([r["net"] for r in A])
        sa = statistics.pstdev([r["net"] for r in A]) / math.sqrt(len(A))
        out("\n  多臂战役逐候选判定（基线 %s，本战役 %d 房）：" % (base, len(A)))
        for st in _cur[1:]:
            B = [r for r in arms[st] if (not cur_started or r.get("ts", "") >= cur_started)]
            is_bundle = st in (bundles or set())
            tag = "组合臂" if is_bundle else "单变量"
            thr = BUNDLE_THRESHOLD if is_bundle else SINGLE_THRESHOLD
            end_n = BUNDLE_ROOMS if is_bundle else SINGLE_ROOMS
            if len(B) < 2:
                out("   - %-12s (%s) 房=%d  （需要 ≥2 房才能算 t）" % (st, tag, len(B)))
                res.append({"strategy": st, "tag": tag, "rooms": len(B), "t": None,
                            "verdict": "sample-too-small"})
                continue
            mb = statistics.mean([r["net"] for r in B])
            sb = statistics.pstdev([r["net"] for r in B]) / math.sqrt(len(B))
            se = math.sqrt(sa * sa + sb * sb)
            t = (mb - ma) / se if se else 0.0
            nmin = min(len(A), len(B))
            verdict, thr, end_n = arm_verdict(t, len(A), len(B), is_bundle)
            if verdict == "drop-arm":
                tip = "⚠ 该臂显著更差（t=%.2f ≤ −3.0）⇒ 建议停臂、维持基线 %s" % (t, base)
            elif verdict == "adopt-early":
                tip = "★ 中期阈值达到 → python -X utf8 tools/ab_adopt.py %s" % st
            elif verdict == "adopt":
                tip = "★ 战役结束判定：采用（%s 阈值 %.2f）→ ab_adopt.py %s" % (tag, thr, st)
            elif verdict == "keep-baseline":
                tip = "战役结束判定：维持基线（t=%.2f < %.2f）" % (t, thr)
            elif verdict == "futility":
                tip = ("⚑ 无效性提前收尾：%d 房/臂但 |t|=%.2f < %.2f ⇒ 判 null，"
                       "建议 ab_ctl.py stop 换下一个束" % (nmin, abs(t), FUTILITY_T))
            else:
                tip = "样本累积中（%d/%d 房，阈值 %.2f）" % (nmin, end_n, thr)
            out("   - %-12s (%s) 房=%d  净胜/房 %+7.1f  差 %+7.1f ±%5.1f  t=%+5.2f  %s"
                % (st, tag, len(B), mb, mb - ma, 1.96 * se, t, tip))
            res.append({"strategy": st, "tag": tag, "rooms": len(B),
                        "mean": mb, "diff": mb - ma, "se": se, "t": t,
                        "threshold": thr, "verdict": verdict})
    except Exception as e:
        out("  （多臂判定不可用：%s）" % str(e)[:60])
    return res


def main():
    """默认**跨战役汇总**：按 `_ab_log.jsonl` 的排批归属把历史上所有排过批的房间都算进来。

    为什么不再按当前战役的 `started` 过滤：① 排批归属本身已经排除了"A/B 之前"的房间；
    ② 正式赛会中断本战役，之后会开新战役——若按 started 过滤，前面积累的几十房会被**丢掉**
    （这一点在赛前尤其致命）。想只看某段窗口可用 `--since "YYYY-MM-DD HH:MM:SS"`。
    """
    since = None
    for i, a in enumerate(sys.argv):
        if a.startswith("--since"):
            since = a.split("=", 1)[1] if "=" in a else (sys.argv[i + 1] if i + 1 < len(sys.argv) else None)
    since = _norm_since(since)
    cfg = None
    if os.path.exists(AB):
        try:
            cfg = json.loads(io.open(AB, encoding="utf-8").read())
        except Exception:
            pass
    if not cfg:
        cfg = {"arms": [sys.argv[1]] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else []}
    global _STARTS
    _STARTS = room_starts()
    by_launch = arm_rooms_from_log(since)
    # ★ 2026-09-16：逐房**因果**对手强度 + 全样本斜率 ⇒ 各臂"调整后净胜/房"（避免把桌差读成策略差）
    _opp = {}
    _beta = 0.0
    try:
        _rows = load_rows(RANKING)
        _opp = opponent_strength(_rows)
        _pts = []
        for _d in _rows:
            if _d.get("status") != "finished":
                continue
            _o = _opp.get(_d.get("room"))
            _m = next((x for x in (_d.get("ranking") or []) if x.get("user_id") == ME), None)
            if _o is None or _m is None:
                continue
            _oth = [x.get("total_score") or 0 for x in (_d.get("ranking") or []) if x.get("user_id") != ME]
            if len(_oth) != 3:
                continue
            _pts.append((_o, (_m.get("total_score") or 0) - sum(_oth) / 3.0))
        if len(_pts) >= 10:
            _beta = slope([a for a, _ in _pts], [b for _, b in _pts])
    except Exception:
        _beta = 0.0
    arm_list = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    # 把历史上排过批、但不在当前配置里的臂也纳入（跨战役汇总）
    for _st in by_launch:
        if _st not in arm_list and _st not in (None, ""):
            arm_list = list(arm_list) + [_st]
    arm_list = [x for x in arm_list if x]
    print("A/B: %s  %s" % (" vs ".join(str(x) for x in arm_list),
                         ("since " + since) if since else "(跨战役全时段)"))
    if INVALID:
        _it = list(INVALID.items())[:3]
        print("  ⚠ 已排除 %d 房**非完成记录**（半房/崩溃快照不计入臂）：%s"
              % (len(INVALID), "; ".join("%s %s %s" % (k[0], k[1], v) for k, v in _it)))
    _all_opp = []
    for _st, _rs in by_launch.items():
        for _d in _rs:
            if _d.get("room") in _opp:
                _all_opp.append(_opp[_d["room"]])
    _base_ostr = statistics.mean(_all_opp) if _all_opp else float("nan")
    arms = {}
    for st in arm_list:
        key = st
        rs = []
        for d in by_launch.get(st, []):
            mine = next((x for x in (d.get("ranking") or []) if x.get("user_id") == ME), None)
            oth = [x.get("total_score") or 0 for x in (d.get("ranking") or []) if x.get("user_id") != ME]
            if mine is None or len(oth) != 3:
                continue
            rs.append({"net": (mine.get("total_score") or 0) - sum(oth) / 3.0,
                       "score": mine.get("total_score") or 0,
                       "rank": mine.get("rank") or 0,
                       "pp": mine.get("place_points") or 0,          # ★ 名次分（§9.59：≠ 原始分）
                       "room": d.get("room"), "ts": d.get("ts")})
        arms[key] = rs
        n = len(rs)
        if n == 0:
            print("  %-14s 尚无可比房间" % st)
            continue
        nets = [r["net"] for r in rs]
        m = statistics.mean(nets)
        se = statistics.pstdev(nets) / math.sqrt(n) if n > 1 else 0.0
        pos = sum(1 for x in nets if x > 0) / n
        avg_rank = statistics.mean([r["rank"] for r in rs])
        durs = []
        for r in rs:
            stt = _STARTS.get(r.get("room"))
            if stt is None:
                continue
            try:
                tt = datetime.datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            mins = (tt - stt).total_seconds() / 60.0
            if 0 < mins < 120:
                durs.append(mins)
        # ★ 房间第一名率（§4c-39）：随机基线 25%，我方历史 18.2%，榜首 42~55%
        _fp = 100.0 * sum(1 for r in rs if (r.get("rank") or 0) == 1) / n
        # ★ 2026-09-16（§9.59）：名次分/房 与 P(top2) —— 正式赛按名次晋级，这两项与原始分**不等价**
        _tp2 = 100.0 * sum(1 for r in rs if (r.get("rank") or 0) <= 2) / n
        _pp = statistics.mean([r.get("pp") or 0 for r in rs])
        _ov = [_opp[r["room"]] for r in rs if r.get("room") in _opp]
        _ostr = statistics.mean(_ov) if _ov else float("nan")
        _allv = [_opp[r["room"]] for r in rs if r.get("room") in _opp]
        _adj = (m - _beta * (_ostr - _base_ostr)) if _ov and _base_ostr == _base_ostr else float("nan")
        if durs:
            med_d = statistics.median(durs)
            # 排行榜是**按时间累计**的 ⇒ 判据应是「净胜/小时」，把房时长/吞吐差算进去。
            per_hour = m * (60.0 / max(1.0, med_d + OVERHEAD_MIN))
            print("  %-14s 房=%3d  净胜/房 %+8.1f ±%5.1f  正分率 %5.1f%%  均名次 %.2f"
                  "  **第一名率 %5.1f%%**  **top2率 %5.1f%%**  名次分/房 %+.2f  房时长中位 %.1f min  **净胜/小时 %+8.1f**"
                  % (st, n, m, 1.96 * se, 100 * pos, avg_rank, _fp, _tp2, _pp, med_d, per_hour))
            print("  %-14s       对手强度/房 %+7.1f（%d/%d 房可估）  **桌强调整后净胜/房 %+8.1f**（β=%+.2f）"
                  % ("", _ostr, len(_ov), n, _adj, _beta))
        else:
            print("  %-14s 房=%3d  净胜/房 %+8.1f ±%5.1f  正分率 %5.1f%%  均名次 %.2f  **第一名率 %5.1f%%**"
                  "  **top2率 %5.1f%%**  名次分/房 %+.2f  对手强度/房 %+7.1f  **调整后净胜/房 %+8.1f**"
                  % (st, n, m, 1.96 * se, 100 * pos, avg_rank, _fp, _tp2, _pp, _ostr, _adj))
    # ★ 判定只针对**当前战役的两臂**：跨战役汇总里会残留已淘汰的臂（实测 2026-09-15：
    #   退役的 speedc130 仍被当成 "b" 打印出 t=-5.25「a 显著更好」，是纯假象）。
    _cur_arms, _cur_started = _current_campaign()
    _bundles = set()          # 组合臂名单（.ab_mode 里的 bundles；缺省空 = 全按单变量）
    if _cur_arms and len(_cur_arms) >= 2 and all(x in arms for x in _cur_arms):
        a = [r for r in arms[_cur_arms[0]] if (not _cur_started or r.get("ts", "") >= _cur_started)]
        b = [r for r in arms[_cur_arms[-1]] if (not _cur_started or r.get("ts", "") >= _cur_started)]
        print("\n  当前战役臂 %s（started=%s）本战役房数：%s"
              % (" vs ".join(_cur_arms), _cur_started or "-",
                 ", ".join("%s=%d" % (x, len([r for r in arms[x]
                     if (not _cur_started or r.get("ts", "") >= _cur_started)])) for x in _cur_arms)))
    else:
        a, b = arms[arm_list[0]], arms[arm_list[-1]]
    try:
        _cfg = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"),
                                  encoding="utf-8").read())
    except Exception:
        _cfg = {}
    _bundles = set(_cfg.get("bundles") or [])
    # ── 预登记**中期采用规则**的状态（操作单 §26.5；写于本战役 1 房/臂时）──
    # 理由：若候选真的好，等到 40h 攒够房数才采用 = 白丢几十小时的收益。
    # 代价：提前看会抬假阳性 ⇒ |t| ≥ 3.0（单次 α≈0.3%）+ 两侧各 ≥12 房；
    # 保护：驱动自带双档熔断（快 6 房/−150、慢 24 房/−50）仍然生效。
    if _cur_arms and len(_cur_arms) >= 2 and len(a) >= 1 and len(b) >= 1:
        _na, _nb = len(a), len(b)
        _win = _cur_arms[-1] if (statistics.mean([r["net"] for r in b]) >
                                 statistics.mean([r["net"] for r in a])) else _cur_arms[0]
        if _na >= 2 and _nb >= 2:
            _sa = statistics.pstdev([r["net"] for r in a]) / math.sqrt(_na)
            _sb = statistics.pstdev([r["net"] for r in b]) / math.sqrt(_nb)
            _se = math.sqrt(_sa * _sa + _sb * _sb)
            _t = (statistics.mean([r["net"] for r in b]) -
                  statistics.mean([r["net"] for r in a])) / _se if _se else 0.0
            if abs(_t) >= 3.0 and min(_na, _nb) >= 12:
                print("  ★ 达到**预登记中期采用阈值**（|t|=%.2f ≥3.00，房数 %d/%d ≥12）："
                      "建议立即采用 **%s**" % (abs(_t), _na, _nb, _win))
                print("    执行：python -X utf8 tools/ab_adopt.py %s" % _win)
            else:
                print("  中期采用阈值未达：|t|=%.2f（需 ≥3.00），房数 %d/%d（需各 ≥12）"
                      % (abs(_t), _na, _nb))
        else:
            print("  中期采用阈值状态：房数 %d/%d（需各 ≥12，且 ≥2 才能算 t）" % (_na, _nb))
    if len(a) >= 3 and len(b) >= 3:
        ma = statistics.mean([r["net"] for r in a])
        mb = statistics.mean([r["net"] for r in b])
        sa = statistics.pstdev([r["net"] for r in a]) / math.sqrt(len(a))
        sb = statistics.pstdev([r["net"] for r in b]) / math.sqrt(len(b))
        se = math.sqrt(sa * sa + sb * sb)
        print("\n  b − a = %+.1f/房  ±%.1f  t=%.2f" % (mb - ma, 1.96 * se, (mb - ma) / se if se else 0))
        delta = 50.0
        # 功率（单位必须与判据一致！）：
        #   每局四家总分恒为 0（实测 19,541/19,541 局、344/344 房），所以
        #       净胜/房 ≡ 我方分 − 另三家均分 = (4/3) × 原始分/房
        #   —— 两者只差一个常数 4/3，判据等价，但**阈值与 SD 必须同单位**。
        #   SD(净胜/房) 实测 194.0；SD(原始分/房) 实测 145.5（= 194.0 ÷ 4/3）。
        #   两臂各 n 房、95% 检出力：D = 1.96·SD·sqrt(2/n)。
        _SD_NET = 194.0
        need50_net = int(2 * (1.96 * _SD_NET / 50.0) ** 2)
        need50_raw = int(2 * (1.96 * (_SD_NET * 0.75) / 50.0) ** 2)
        print("  功率参考（净胜/房 单位）：判 ±50 需 ~%d 房/臂；±%.0f 需 ~%d 房/臂"
              % (need50_net, delta, int(2 * (1.96 * _SD_NET / max(delta, 1e-9)) ** 2)))
        print("  同口径换成**原始分/房**（排行榜实际计分单位）：±50 需 ~%d 房/臂。"
              % need50_raw)
        print("  换算：净胜/房 恒等于 4/3 × 原始分/房（房内四家和恒为 0，实测 100%）。")
        _t = (mb - ma) / se if se else 0.0
        # ── 预登记**中期采用规则**（操作单 §26.5，写于本战役第 1 房/臂时）──
        # 理由：若候选真的好，等 40h 攒够 80 房/臂 才采用 = 白丢几十小时的收益
        #      （每房 100 分 × 剩余小时数 × 4 房/h 都是真金白银）。
        # 代价：提前看会增加假阳性 ⇒ 阈值取 |t| ≥ 3.0（单次 α≈0.3%）+ 两侧各 ≥12 房。
        # 保护：驱动自带的双档熔断（快 6 房/−150、慢 24 房/−50）仍生效。
        _nmin = min(len(a), len(b))
        # ⚠ .ab_mode 缺失（战役已结束/被熔断终止）时 _cur_arms 是 None ⇒ 以前这里会 TypeError 崩掉。
        # 实测 2026-09-16 11:16：c073w4 触发熔断终止战役，随后 ab_readout 直接抛 TypeError。
        if not _cur_arms:
            print("  ⚠ 当前没有进行中的战役（var/.ab_mode 不存在）——上面是跨战役全时段累计，不是单次战役读数。")
            print("    起始新战役：python -X utf8 tools/ab_ctl.py start <基线>,<候选> --bundles=<候选>")
            multi_arm_report(arms, _cur_arms, _cur_started, set(_cfg.get("bundles") or []), out=print)
            print("\n提示：各臂轮转排批（每房轮换）⇒ 同池同时段；顺序比较在本作 ±180/房 的日间漂移下无意义。")
            return
        _win = _cur_arms[-1] if mb > ma else _cur_arms[0]
        if abs(_t) >= 3.0 and _nmin >= 12:
            print("  ★ 达到**预登记中期采用阈值**（|t|=%.2f≥3.00 且各臂 %d/%d 房 ≥12）："
                  "建议立即采用 **%s**" % (abs(_t), len(a), len(b), _win))
            print("    执行：python -X utf8 tools/ab_adopt.py %s" % _win)
        else:
            print("  中期采用阈值未达：|t|=%.2f（需 ≥3.00）  各臂房数 %d/%d（需 ≥12）"
                  % (abs(_t), len(a), len(b)))
        print("  判定：%s" % ("尚无结论" if abs((mb - ma) / se if se else 0) < 1.96 else
                            ("b 显著更好" if mb > ma else "a 显著更好")))
        # 两臂战役的**显式终点判定**（组合臂 1.50/150 房，单变量 1.96/100 房）
        _is_bundle = bool(_cur_arms and len(_cur_arms) == 2 and _cur_arms[1] in _bundles)
        _v2, _thr2, _end2 = arm_verdict(_t, len(a), len(b), _is_bundle)
        _tag2 = "组合臂" if _is_bundle else "单变量"
        if _v2 == "drop-arm":
            print("  ⚠ 该臂显著更差（t=%.2f ≤ −3.00，各 %d/%d 房）⇒ 建议停战役、维持基线："
                  "python -X utf8 tools/ab_ctl.py stop" % (_t, len(a), len(b)))
        elif _v2 == "adopt-early":
            print("  ★ 达到**预登记中期采用阈值**（t=%.2f ≥3.00，各 %d/%d 房）⇒ 采用 %s："
                  "python -X utf8 tools/ab_adopt.py %s"
                  % (_t, len(a), len(b), (_cur_arms[-1] if _t > 0 else _cur_arms[0]),
                     (_cur_arms[-1] if _t > 0 else _cur_arms[0])))
        # ── 预登记「无效性提前收尾」规则（2026-09-17 新增，见 STATUS §4c-27）──
        #    在 >=100 房/臂时，若 |t| < 0.6，即便再跑满 150 房/臂，期望 |t| 也只有 0.73
        #    （|t| 随 sqrt(n) 增长 1.22 倍）⇒ 基本不可能达到组合臂阈值 1.5，
        #    而继续跑要再花 ~100 房（≈2 人的实验税）⇒ 提前判 null、把房让给下一个束。
        if _v2 == "futility":
            print("  ⚑ 无效性提前收尾：各 %d 房/臂但 |t|=%.2f < %.2f ⇒ 判 null、停战役"
                  "（继续跑到 %d 房的期望 |t| 只有 %.2f < 阈值 %.2f）"
                  % (_nmin, abs(_t), FUTILITY_T, _end2, abs(_t) * 1.2247, _thr2))
            print("    执行：python -X utf8 tools/ab_ctl.py stop  然后按分岔接下一个束")
        if _nmin >= _end2:
            if _t >= _thr2:
                print("  ★ 战役结束判定（%s，阈值 %.2f，已 %d/%d 房）：**采用 %s** → "
                      "python -X utf8 tools/ab_adopt.py %s"
                      % (_tag2, _thr2, len(a), len(b), _win, _win))
            else:
                print("  战役结束判定（%s，阈值 %.2f，已 %d/%d 房）：**维持基线 %s**"
                      "（t=%.2f）→ python -X utf8 tools/ab_ctl.py stop"
                      % (_tag2, _thr2, len(a), len(b), _cur_arms[0] if _cur_arms else "?",
                         _t))
        else:
            print("  终点判定还需：%s %d 房/臂（当前 %d/%d，阈值 %.2f）"
                  % (_tag2, _end2, len(a), len(b), _thr2))
    multi_arm_report(arms, _cur_arms, _cur_started, set(_cfg.get("bundles") or []),
                     out=print)
    print("\n提示：各臂轮转排批（每房轮换）⇒ 同池同时段；顺序比较在本作 ±180/房 的日间漂移下无意义。")


if __name__ == "__main__":
    main()
