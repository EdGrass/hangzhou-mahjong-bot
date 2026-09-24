# -*- coding: utf-8 -*-
"""并发交替真机 A/B 驱动（`.ab_mode` 存在时接管排批）。

为什么必须"交替"：真机对手池/时段漂移可达 ±180/房（项目自己的记录），
顺序比较（A 跑一天、再 B 跑一天）在这个量级下没有意义。交替排批让两条臂
**处在同一批对手、同一时段**，差值才有意义。

安全设计（与 `.official_mode` 同一模式）：
- 只在「当前没有 match_super 且没有 run_bot」时启动下一批（绝不并发 → 不撞 E002）；
- 启动前确保没有 keeper 在跑（keeper 也会起 match_super，会双开）；
- `.official_mode` 优先级更高：官方赛期间本驱动直接退出；
- `.ab_mode` 一旦被删除（`tools/ab_ctl.py stop`），本轮结束后驱动自行退出，
  watchdog 会照常把 keeper 拉回来。

配置 `var/.ab_mode`（JSON）：{"a": "speedtugc", "b": "speedc130", "rooms": 1}
单次日志：`var/_ab_log.jsonl`（每批一行：ts / arm / strategy）
"""
from __future__ import annotations
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")
STATE = os.path.join(ROOT, "var", "_ab_state_v2.json")   # 与旧 _keeper_ab.py 的 _ab_state.json 分开，保留其历史
LOG = os.path.join(ROOT, "var", "_ab_log.jsonl")
KEEPER_STRAT = os.path.join(ROOT, "var", "_keeper_strategy.txt")
try:
    import psutil
except Exception:
    psutil = None
sys.path.insert(0, os.path.join(ROOT, "var"))
import _feature_mode as _fm  # noqa: E402


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with io.open(os.path.join(ROOT, "var", "_ab_driver.out"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def procs(name):
    out = []
    if psutil is None:
        return out
    for p in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            for a in (p.info.get("cmdline") or [])[1:]:
                if os.path.basename(str(a).replace("\\", "/")) == name:
                    out.append(p.info["pid"])
                    break
        except Exception:
            pass
    return out


def read_cfg():
    try:
        return json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return None


def read_state():
    try:
        return json.loads(io.open(STATE, encoding="utf-8").read())
    except Exception:
        return {}


def arms_of(cfg):
    """支持 N 臂：cfg["arms"]=[...]；仍兼容旧的 {"a":..,"b":..}。"""
    if isinstance(cfg.get("arms"), list) and len(cfg["arms"]) >= 2:
        return [str(x) for x in cfg["arms"]]
    return [cfg.get("a"), cfg.get("b")]


def pick_arm(st, arms):
    """返回 (index, label)；兼容旧状态里的 {"next": "a"|"b"}。"""
    n = len(arms)
    if "next_idx" in st:
        i = int(st["next_idx"]) % n
    elif st.get("next") in ("a", "b"):
        i = 0 if st["next"] == "a" else 1
    else:
        i = 0
    return i, arms[i]


def write_state(st):
    with io.open(STATE, "w", encoding="utf-8") as f:
        f.write(json.dumps(st, ensure_ascii=False))


def once_dry():
    """只做一次「选臂 + 写状态/日志」，打印将要执行的命令，**不启动任何进程、不杀任何进程**。
    用于验证交替逻辑，而不扰动线上。"""
    cfg = read_cfg()
    if not cfg:
        print("无 .ab_mode 配置"); return 1
    rooms = str(int(cfg.get("rooms", 1)))
    arms = arms_of(cfg)
    st = read_state()
    i, strat = pick_arm(st, arms)
    arm = strat
    st["next_idx"] = (i + 1) % len(arms)
    cnt = st.setdefault("counts", {})      # 注意：RHS 会先求值，必须先取出引用
    cnt[arm] = cnt.get(arm, 0) + 1
    write_state(st)
    cmd = [sys.executable, "-X", "utf8", "-u",
           os.path.join(ROOT, "tools", "match_super.py"), "--rooms", rooms, "--strategy", strat]
    print("arm=%s strategy=%s rooms=%s" % (arm, strat, rooms))
    print("would run:", " ".join(cmd))
    print("next arm ->", arms[st["next_idx"]], " counts=", st["counts"])
    return 0


GUARD_MIN_ROOMS = 6          # 快档：差值至少这么多房才判（2026-09-20 由 4 改 6：见 R699）
GUARD_NET = -300.0           # 快档阈值（候选−基线，6 房差值 SE≈112 ⇒ -300 ≈ 2.7σ；R699 用 83 次历史回放校准）
GUARD_MILD_ROOMS = 12        # 慢档：12 房后判
GUARD_MILD_NET = -150.0      # 慢档阈值（12 房差值 SE≈79 ⇒ -150 ≈ 1.9σ）
ME_ID = "u_7a3fba48d70b"


def arm_recent_net(strategy, since):
    """候选臂自 A/B 开始以来的净胜/房（用榜单权威数据，不需复盘）。"""
    nets = []
    try:
        for ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("strategy") != strategy:
                continue
            if since and d.get("ts", "") < since:
                continue
            rk = d.get("ranking") or []
            mine = next((x for x in rk if x.get("user_id") == ME_ID), None)
            oth = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME_ID]
            if mine is None or len(oth) != 3:
                continue
            nets.append((mine.get("total_score") or 0) - sum(oth) / 3.0)
    except OSError:
        pass
    return nets


def arm_recent(strategy, since, k):
    """候选/基线臂**最近 k 房**的 net 列表（末尾 k 条）。"""
    return arm_recent_net(strategy, since)[-k:]


def guard_candidate(strategy, baseline, since):
    """返回 (abort?, 展示用均值, 房数, 基线均值)。两档，判的是**候选 − 基线**：

    ★ 2026-09-16 修正（此前是**绝对阈值**，有真实缺陷）：
      旧实现在"候选臂近 4 房均值 < -150"时就熔断——但候选的**绝对** net 受房间运气/对手强度影响极大
      （房级 SD ≈194 净胜/房 ⇒ 4 房均值 SE ≈ 97），一个**与基线完全相同**的候选也有 ~6% 的概率触发，
      在一个上百房的战役里会累积成"**噪声杀**"。而它抓 speedE 那次（−263/房）其实用**差值**看同样明显。
      ⇒ 改成 `候选近 k 房均值 − 基线同期近 k 房均值`，并用**校准过的阈值**：
        4 房差值的 SE ≈ `194·√2/2 = 137` ⇒ 阈值 -300 ≈ 2.2σ；
        12 房差值的 SE ≈ `194·√2/√12 = 79` ⇒ 阈值 -150 ≈ 1.9σ。
      设计意图：熔断器只做**灾难兜底**（抓 speedE 那种 −200/房级别的崩坏），
      "慢性小亏"交给预登记判据（终点 |t| / 采用阈值），不再指望熔断器抓 −30~−60 的小亏——
      因为在房级 SD 194 的现实下，那个阈值必然误伤。

    ★ 2026-09-20 修正二（R699）：`GUARD_MIN_ROOMS` 4 ⇒ 6（阈值 -300 不变）。
      用 23 段历史战役的**真实交叉排批数据回放**本统计量（83 次检查）：
        · k=4  ：2 次 < -300 —— 两条都发生在 2026-09-20，同一次战役里 c151 触发 -488、c191 触发 -475；
        · k=6/8/10/12：**0 次** < -300（k=6 的 min=-140、k=12 的 min=-46）。
      而被熔断的 c191 是**机制未生效**的臂（R697：覆盖率 Δ=-0.8pp，门禁未过），却与 c151 同幅度触发
      ⇒ 该统计量当时量的是**窗口**（基线连吃两房 +632），不是臂。
      ⇒ 快档 4 房提到 6 房（k=6 差值 SE≈112 ⇒ -300 ≈ 2.7σ）；慢档 12/-150 不动。
    """
    cand = arm_recent(strategy, since, max(GUARD_MIN_ROOMS, 12))
    base = arm_recent(baseline, since, max(GUARD_MIN_ROOMS, 12)) if baseline else []
    n = min(len(cand), len(base)) if base else 0
    if n >= GUARD_MIN_ROOMS:
        m = (sum(cand[-GUARD_MIN_ROOMS:]) - sum(base[-GUARD_MIN_ROOMS:])) / GUARD_MIN_ROOMS
        if m < GUARD_NET:
            return True, m, GUARD_MIN_ROOMS, (sum(base[-GUARD_MIN_ROOMS:]) / GUARD_MIN_ROOMS)
    if n >= GUARD_MILD_ROOMS:
        m = (sum(cand[-GUARD_MILD_ROOMS:]) - sum(base[-GUARD_MILD_ROOMS:])) / GUARD_MILD_ROOMS
        if m < GUARD_MILD_NET:
            return True, m, GUARD_MILD_ROOMS, (sum(base[-GUARD_MILD_ROOMS:]) / GUARD_MILD_ROOMS)
    if not n:
        # 基线数据缺失（例如战役刚开始）⇒ 退回绝对口径的**只读展示**，不熔断
        nets = arm_recent_net(strategy, since)
        return False, (sum(nets) / len(nets) if nets else 0.0), len(nets), 0.0
    cm = sum(cand[-n:]) / n
    bm = sum(base[-n:]) / n
    return False, cm - bm, n, bm


def last_batch_bad(strategy, since, path=None):
    """★ 2026-09-16 新增：上一批是否**异常结束**（没落盘 / status≠finished / exit_code≠0 / 局数≠80）。

    为什么必须知道：平台 `/api/match` **幂等**（"绝不双房双席"）—— 若上一批崩了但**房还在跑**，
    下一批会被**拉回同一个房**。此时若换了臂，就会产生"一房两臂"的脏样本：
    实测 2026-09-16 19:23 一次离线重放 OOM 杀掉了候选臂的 run_bot，下一批（基线臂）被拉进同一房
    （房 a_0aca4ad1f990 前 23 手候选 / 其余基线）⇒ 两臂各丢一个房、且污染读数（t 从 0.60 虚高到 1.12）。
    返回 (bad, why)。
    """
    path = path or os.path.join(ROOT, "var", "auto_ranking.jsonl")
    rows = []
    try:
        for ln in io.open(path, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("strategy") != strategy:
                continue
            if since and d.get("ts", "") < since:
                continue
            rows.append(d)
    except OSError:
        return False, ""
    if not rows:
        return True, u"无归档记录"
    d = rows[-1]
    if d.get("status") != "finished":
        return True, u"status=%s" % d.get("status")
    if d.get("exit_code") not in (0, None):
        return True, u"exit_code=%s" % d.get("exit_code")
    for x in (d.get("ranking") or []):
        if x.get("games_played") not in (None, 80):
            return True, u"games_played=%s" % x.get("games_played")
    return False, u""


def arm_extra_args(strategy, cfg, wait_cfg_path=None):
    """★ 2026-09-16：把 `.ab_mode.arm_opts` 里的**逐臂**选项翻成 match_super 的命令行参数。

    例：`arm_opts = {"speedtugc_w50": {"wait_until_second": 50}}` ⇒ 该臂启动时追加
    `--wait-until-second 50`（"入席秒 ↔ 同桌强度"预登记实验用，STATUS §9.87）。
    未配置的臂返回 []（默认行为不变）。
    """
    try:
        opts = (cfg or {}).get("arm_opts") or {}
        o = opts.get(strategy) or {}
    except Exception:
        return []
    out = []
    if isinstance(o.get("wait_until_second"), int):
        out += ["--wait-until-second", str(int(o["wait_until_second"]))]
        return out
    # ★ 2026-09-17：**没有逐臂显式设置时，跟随全局开关** `var/.wait_until_second`
    #   （keeper 链早就读它；此前 A/B 驱动不读 ⇒ 若池子实验成立、全局启用等待，
    #    战役期间（由驱动排批）反而**不会**等待 ⇒ 白白丢掉池子收益）。
    #   设全局等待时**所有臂一起等** ⇒ A/B 对照仍然公平。
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from wait_policy import wait_args
        return list(wait_args(wait_cfg_path)) if wait_cfg_path else list(wait_args())
    except Exception:
        return out


def other_driver_pids(procs_cmdlines, me_pid):
    """纯函数：给 [(pid, cmdline), …]，返回**除自己以外**的 `_ab_driver.py` 进程 pid 列表。"""
    out = []
    for pid, argv in procs_cmdlines or []:
        if pid == me_pid:
            continue
        for a in list(argv or [])[1:]:
            base = os.path.basename(str(a).replace("\\", "/")).lower()
            if base == "_ab_driver.py":
                out.append(pid)
                break
    return out


def _other_drivers():
    """本机除自己以外的 `_ab_driver.py` 进程（★ 2026-09-17：防"两驱动同排批 = E002"）。"""
    try:
        import psutil
    except Exception:
        return []
    seen = []
    for p in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            seen.append((p.info.get("pid"), p.info.get("cmdline") or []))
        except Exception:
            pass
    return other_driver_pids(seen, os.getpid())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--once-dry":
        return once_dry()
    # ★★ 2026-09-17 自守卫（E002）：库里已有另一个驱动在跑 ⇒ **本实例立刻退出、绝不写基线**。
    #   为什么需要：`_watchdog` 在 A/B 模式也会"缺驱动就拉起"，它与 `ab_ctl.py start` 之间有
    #   极窄的竞态（watchdog 每 90s 检查一次、start 写哨兵到 spawn 之间有几十毫秒）
    #   ⇒ 两个驱动都看到同一份 `.ab_mode` 并各自排批 ⇒ 同账号两房并发 = E002。
    #   与 `_official_keepalive.py` 的"已有进程就拒绝"同一思路；幂等由本守卫保证。
    others = _other_drivers()
    if others:
        log("检测到另一个 _ab_driver 在跑（pid=%s）→ 本实例立即退出（防两驱动同排批 = E002）"
            % ",".join(str(x) for x in others))
        return 0
    cfg = read_cfg()
    if not cfg:
        log("无 .ab_mode 配置，退出")
        return 1
    arms = arms_of(cfg)
    if len(arms) < 2 or not all(arms):
        log("配置缺 arms（或 a/b），退出")
        return 1
    a = arms[0]                      # 基线 = 第 1 臂
    rooms = str(int(cfg.get("rooms", 1)))
    st = read_state()
    log("A/B 启动：arms=%s rooms=%s（基线 %s）" % ("/".join(arms), rooms, a))
    idle = 0
    while os.path.exists(AB):
        if _fm.pause_requested():
            try:
                io.open(KEEPER_STRAT, "w", encoding="utf-8").write(a)
            except Exception:
                pass
            log("平台暂停模式（.pause_mode）→ A/B 驱动退出（基线 %s）" % a)
            return 0
        if os.path.exists(OFFICIAL):
            try:
                io.open(KEEPER_STRAT, "w", encoding="utf-8").write(a)
            except Exception:
                pass
            log("官方赛模式已开启 → A/B 驱动退出（策略文件已恢复为基线 %s）" % a)
            return 0
        # keeper 会自己起 match_super，双开会撞 E002
        for pid in procs("_keeper.py"):
            try:
                psutil.Process(pid).kill()
                log("杀掉 keeper pid=%d（避免双开 match_super）" % pid)
            except Exception:
                pass
        ms = procs("match_super.py")
        rb = procs("run_bot.py")
        if ms or rb:
            idle = 0
            time.sleep(15)
            continue
        idle += 1
        if idle < 2:              # 连续两次确认空档，避免撞上刚退出的瞬间
            time.sleep(10)
            continue
        idle = 0
        _i, strat = pick_arm(st, arms)
        # ★ 2026-09-16：上一批异常结束时**保持同臂重跑** —— 平台 /api/match 幂等会把这一批
        # 拉回**同一个房**，换臂就会造出"一房两臂"的脏样本（见 last_batch_bad 注释）。
        _prev = st.get("last_strat")
        if _prev and _prev in arms:
            _bad, _why = last_batch_bad(_prev, st.get("last_launch_ts"))
            if _bad:
                log(u"!! 上一批 %s 异常结束（%s）⇒ 同臂重跑（避免把下一臂拉进同一房）" % (_prev, _why))
                strat = _prev
                _i = arms.index(_prev)
        arm = strat
        # 自保：任一候选臂（非基线）近况崩坏 → 立即终止 A/B 并回退到基线
        if strat != a:
            abort, gmean, gn, gbase = guard_candidate(strat, a, cfg.get("started"))
            if abort:
                log("!! 候选臂 %s 近 %d 房「净值 − 基线净值」%+.1f/房（基线同期 %+.1f）触发熔断 → 终止 A/B，回退基线 %s"
                    % (strat, gn, gmean, gbase, a))
                try:
                    io.open(KEEPER_STRAT, "w", encoding="utf-8").write(a)
                except Exception:
                    pass
                if os.path.exists(AB):
                    os.remove(AB)
                return 0
        try:
            io.open(KEEPER_STRAT, "w", encoding="utf-8").write(strat)
        except Exception:
            pass
        try:
            # 每批落一个 _ab_run_<ts>.out —— 否则批次失败（如服务器 502/404 清房）
            # 会**静默消失**，无从判断是平台问题还是候选策略问题。
            _out = io.open(os.path.join(ROOT, "var", "_ab_run_%s.out"
                                        % time.strftime("%Y%m%d_%H%M%S")),
                           "a", encoding="utf-8")
            subprocess.Popen([sys.executable, "-X", "utf8", "-u",
                              os.path.join(ROOT, "tools", "match_super.py"),
                              "--rooms", rooms, "--strategy", strat]
                             + arm_extra_args(strat, cfg),
                             cwd=ROOT, stdout=_out, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            st["next_idx"] = (_i + 1) % len(arms)
            st["last_strat"] = strat
            st["last_launch_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
            cnt = st.setdefault("counts", {})
            cnt[arm] = cnt.get(arm, 0) + 1
            write_state(st)
            with io.open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "arm": arm, "strategy": strat, "rooms": rooms}) + "\n")
            log("已排批 arm=%s strategy=%s rooms=%s（累计 %s）"
                % (arm, strat, rooms, st["counts"]))
        except Exception as e:
            log("启动批次失败：%s" % e)
        time.sleep(20)
    # 退出前把基线写回策略文件：否则 A/B 结束后 keeper 可能直接接着跑**候选**（未验证）
    try:
        io.open(KEEPER_STRAT, "w", encoding="utf-8").write(a)
        log("退出前已将策略文件恢复为基线 %s（避免生产停在未验证的候选上）" % a)
    except Exception as e:
        log("恢复基线策略失败：%s" % e)
    log("`.ab_mode` 已删除 → A/B 驱动退出（watchdog 将恢复 keeper）")
    return 0


if __name__ == "__main__":
    import traceback
    while True:
        try:
            sys.exit(main())
        except SystemExit:
            raise
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception:
            try:
                log("!! A/B 驱动异常退出，5s 后重启：\n%s" % traceback.format_exc()[-800:])
            except Exception:
                pass
            time.sleep(5)
