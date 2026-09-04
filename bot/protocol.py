"""v8 多阶段锦标赛状态机与主循环。

进度真相 = GET /api/tournaments/{id} 的 status（唯一权威）：
    registering → running → stage_done → stage_open → running → …（决赛轮）→ finished
    任时可 closed / void；running 中断收敛落 stage_done + stage_crashed=true。

打完一个阶段 ≠ 结束：晋级轮打完 stage_done（等管理员推进）、新阶段 stage_open
（名单内 ready = 出席确认，每阶段重新确认）、决赛并列自动加赛（running 内新
game_id 自动出现，含 _s{k} 段标识）。只有 finished/closed/void 才退出。

本模块的 tournament_intent() 是纯函数（可单测）：把锦标赛详情映射为意图，
主循环按意图执行。
"""
from __future__ import annotations

import threading
import time
import urllib.error

from .api import ApiError
from .game import play_game
from .model import TERMINAL_STATUSES
from .util import log

# 状态机行为参数
POLL_INTERVAL = 1.0            # 锦标赛详情轮询间隔（秒，running 等需要反应性的状态）
REGISTER_POLL = 15.0           # 报名期稳态轮询（开赛秒级感知足够，降 90%+ 请求）
STAGE_WAIT_POLL = 5.0          # stage_done 等管理员推进（分钟~小时级）
UNKNOWN_STATUS_INTERVAL = 5.0  # 未知状态（版本前向兼容）的保守轮询间隔
JOIN_GIVE_UP_SEC = 300.0       # 一直无法入场的放弃时间（错过报名/名额满）


def _stage(t):
    """阶段对象与顶层 stage_* 字段的统一读取（字段组位置见 §2.6，两种形态都兼容）。"""
    s = t.get("stage")
    if not isinstance(s, dict):
        s = {}
    return {"no": s.get("no"), "role": s.get("role"), "total": s.get("total"),
            "name": s.get("name") or "",
            "crashed": bool(t.get("stage_crashed")) or bool(s.get("crashed"))}


def tournament_intent(t):
    """纯函数：锦标赛详情 → (intent, 说明)。

    intent ∈ exit | register | confirm | wait | play | eliminated | unknown
    - exit       终态（finished/closed/void）
    - register   报名期：报名 + 到位
    - confirm    阶段确认期 stage_open 且我有本阶段资格 → ready 出席确认
    - eliminated stage_open 名单外（海选已淘汰/未报名）→ 本锦标赛与我无关，退出
    - wait       晋级轮打完等推进 / 阶段间隙空转（≠ 结束，继续轮询）
    - play       running：收割活跃场次（含决赛加赛自动出现的新场）
    - unknown    未知 status（服务器升级前向兼容）：保守轮询并告警
    """
    status = t.get("status")
    if status in TERMINAL_STATUSES:
        return "exit", status
    if status == "registering":
        return "register", "报名期"
    if status == "stage_open":
        # 阶段 2+ 确认期。例外：阶段 1 崩溃重赛的确认期报名全量 qualified=true、role 空
        if t.get("qualified"):
            return "confirm", "阶段确认期(%s)" % _stage(t)["name"]
        return "eliminated", "未获得本阶段资格（已淘汰）"
    if status == "stage_done":
        st = _stage(t)
        hint = "中断待重赛" if st["crashed"] else "等管理员推进"
        return "wait", "晋级轮打完(%s)：%s" % (st["name"] or "?", hint)
    if status == "running":
        return "play", "running(%s)" % (_stage(t)["name"] or "?")
    return "unknown", "未知 status=%r（需人工核对指南版本）" % (status,)


def active_game_ids(client, tid, t):
    """本锦标赛的活跃场次：/api/me active_games ∩ my_games（历史累计）交集过滤。
    报名令牌 /api/me 已限定；全局令牌靠交集过滤掉别人的场；决赛加赛新场也在其中。"""
    me = client.me()
    act = [g["game_id"] for g in (me.get("active_games") or []) if isinstance(g, dict)]
    mine = set(t.get("my_games") or [])
    if mine:
        return [g for g in act if g in mine]
    return act


def _play_concurrent(client, gids, strategy):
    """并发打多场（M 上限内 active_games 同时多场：长轮询各自推进，防超时代打）。

    每场一个 daemon 线程跑 play_game；瞬断类错误在线程内已自愈，
    其它异常收集后由主线程记录（不阻断其余场次）。返回异常列表。
    """
    errors = []
    lock = threading.Lock()

    def worker(gid):
        try:
            play_game(client, gid, strategy)
        except ApiError as e:
            with lock:
                errors.append((gid, e))

    threads = []
    for gid in gids:
        t = threading.Thread(target=worker, args=(gid,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()               # 等待全部场次结束（各自事件驱动）
    for gid, e in errors:
        log("场次 %s 异常终止: %s %s", gid, e.status, (e.code or e.body)[:160])
    return errors


def run_tournament(client, tid, strategy, scoped=True):
    """锦标赛主循环（阻塞直到 finished/closed/void 或确定与我无关）。"""
    registered_in_period = False    # 是否已成功报名+到位（幂等；报名期成功一次即可，也用于 403 未入场判定）
    last_confirm_at = 0.0           # 上次出席确认时间 —— 确认幂等(200)，仅做节流防每秒刷
    give_up_at = time.time() + JOIN_GIVE_UP_SEC
    last_state = (None, None, None)     # 上次 (status, 阶段名, crashed)——状态变化才打印
    last_heartbeat = 0.0                # 心跳日志（长时间同态时每 60s 一行）
    log("锦标赛主循环启动: tid=%s", tid)

    while True:
        try:
            t = client.tournament(tid)
        except ApiError as e:
            if e.status == 0 or e.status >= 500:
                log("锦标赛详情瞬时故障(%s)，重试…" % (e.code or e.status))
                time.sleep(POLL_INTERVAL)
                continue
            if e.status == 403 and not registered_in_period:
                # 非参赛者查详情 403（如全局令牌自测路径报名前）：先尝试幂等进场再看
                log("详情 403（未入场），尝试注册进场…")
                try:
                    client.register(tid)
                    client.ready(tid)
                    registered_in_period = True
                    continue
                except ApiError:
                    pass
                if time.time() > give_up_at:
                    log("长时间无法入场（报名已截止/名额已满），退出")
                    return None
                time.sleep(POLL_INTERVAL)
                continue
            raise

        st = _stage(t)
        intent, why = tournament_intent(t)
        state_key = (t.get("status"), st["name"], st["crashed"])
        now = time.time()
        if state_key != last_state or now - last_heartbeat >= 60:
            log("status=%s 阶段=[%s] 意图=%s（%s）" % (
                t.get("status"), st["name"] or "-", intent, why))
            last_state = state_key
            last_heartbeat = now
        if st["crashed"] and intent in ("wait", "play"):
            log("⚠ stage_crashed=true：中断待重赛，继续轮询直至重赛场次出现")

        if intent == "exit":
            if t.get("status") == "finished":
                # 终态兜底判定：测试房间跨轮复用（finished 后 ready 幂等累积，
                # 4 令牌齐备自动开新一轮）；正式锦标赛 finished 后 ready 409 → 退出
                try:
                    client.ready(tid)
                except ApiError as e:
                    if e.status == 409:
                        summary(client, tid, t)
                        return t
                    time.sleep(5)
                    continue
                log("测试房间 finished：跨轮待机（每 5s ready，等待新一轮）…")
                time.sleep(5)
                continue
            summary(client, tid, t)
            return t
        if intent == "register":
            if not registered_in_period:
                # 报名+到位幂等：本报名期成功一次即可，之后纯轮询等开赛
                registered_in_period = _register(client, tid)
            time.sleep(REGISTER_POLL)   # 报名期稳态轮询（低频率）
        elif intent == "confirm":
            # 出席确认幂等(200)，10s 节流即可；即使中途崩溃重赛回同一阶段也会重新确认
            now = time.time()
            if now - last_confirm_at >= 10.0:
                ok = _confirm(client, tid)
                if not ok:
                    log("名单外 NOT_QUALIFIED：无本阶段资格，本锦标赛与我无关，退出")
                    return t
                last_confirm_at = now
            time.sleep(POLL_INTERVAL)
        elif intent == "eliminated":
            log("已淘汰：本阶段名单外（海选未晋级/未报名），本锦标赛与我无关，退出")
            return t
        elif intent == "play":
            try:
                acts = active_game_ids(client, tid, t)
            except ApiError as e:
                if e.status == 0 or e.status >= 500:
                    log("活跃场查询瞬时故障(%s)，重试…" % (e.code or e.status))
                    time.sleep(1.0)
                    continue
                raise
            if acts:
                # 多场并发（同一桌位事件驱动互不阻塞），全部结束后立刻复查
                _play_concurrent(client, acts, strategy)
                continue        # 同批余场/决赛加赛新场可能刚出现
            time.sleep(POLL_INTERVAL)
        elif intent == "wait":
            time.sleep(STAGE_WAIT_POLL)     # 等管理员推进：分钟~小时级，低频轮询
        else:  # unknown：保守轮询（版本前向兼容），不退出
            time.sleep(UNKNOWN_STATUS_INTERVAL)


def _register(client, tid):
    """报名期：幂等报名 + 到位；409 竞态（恰逢开赛/已关闭）吞掉回主循环按最新状态处理。
    返回是否已成功到位。"""
    ok = False
    for name, fn in (("报名", client.register), ("到位", client.ready)):
        try:
            fn(tid)
            log("已%s（幂等）" % name)
            ok = ok or name == "到位"
        except ApiError as e:
            if e.status == 409:
                log("%s被拒(竞态):" % name, e.code or e.body[:120])
            else:
                raise
    return ok


def _confirm(client, tid):
    """阶段 2+ 确认期：ready = 出席确认（幂等 200；每阶段都要重新确认）。
    返回 False 表示名单外（NOT_QUALIFIED = 已淘汰）。"""
    try:
        client.ready(tid)
        log("已确认出席本阶段（幂等）")
        return True
    except ApiError as e:
        if e.status == 409:
            log("确认被拒:", e.code or e.body[:120])
            return e.code != "NOT_QUALIFIED"
        raise


def summary(client, tid, t):
    """终态汇总：输出本人排名（若可见）。"""
    log("锦标赛结束: status=%s" % t.get("status"))
    try:
        uid = client.me().get("user_id")
    except (ApiError, urllib.error.URLError):
        uid = None
    ranking = t.get("ranking") or []
    if uid and ranking:
        for r in ranking:
            if r.get("user_id") == uid:
                log("我的最终排名: rank=%s total_score=%s place_points=%s "
                    "god_count=%s games_played=%s" % (
                        r.get("rank"), r.get("total_score"), r.get("place_points"),
                        r.get("god_count"), r.get("games_played")))
                return
    log("最终排名不可见或榜内无我（共 %d 条）" % len(ranking))
