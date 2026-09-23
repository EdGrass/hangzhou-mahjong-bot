"""单局（场次）主循环：seq 长轮询 / 快照权威 / 动作提交与竞态恢复。

协议要点（指南 §2.1）：
- seq=S 的响应已含全部 ≤S 事件，快照是规范真相；
- 快照无 allowed_actions —— 动作合法性由策略层自行判断，服务端纯验证；
- 丢帧（gap）/ 动作 409 后，用 seq=0 重建全量快照；
- 窗口「已响应」须客户端本地跟踪，重复提交 pass/动作返回 409 INVALID_ACTION。
"""
from __future__ import annotations

import json
import os
import time

from .api import ApiError
from .meldtrack import MeldTracker
from .model import my_turn, snap_view, window_pending
from .util import log


def _dr_payload(gid, view, seq, river, ms, act, age_ms=None, rnd=None):
    """决策记录载荷（紧凑键）：完整信息局面 + 动作 + 决策耗时。

    k=d 决策行；s/p/t/q=seat/phase/turn/seq；h=决策手牌（含刚摸）；d/o=刚摸/
    offer；m=副露[(type,tile)]；god=爆头/链/飘/抓打；r=当局公开河；a=动作；
    ms=decide 耗时(ms)；sub/sm=提交结果/耗时（game.py 提交后补填）。
    """
    melds = view.get("melds") or []
    god = view.get("god") or {}
    return {"k": "d", "g": gid, "s": view.get("seat"), "p": view.get("phase"),
            "t": view.get("turn"), "q": int(seq or 0),
            "rs": list(view.get("responding_seats") or []),
            "h": list(view.get("my_hand") or []),
            "d": view.get("drawn_tile"), "o": view.get("offer_tile"),
            "m": [[x.get("type"), x.get("tile")] for x in melds],
            "god": {"b": bool(god.get("baotou")),
                    "cc": int(god.get("chain_count") or 0),
                    "piao": int(god.get("piao_count") or 0),
                    "cp": bool(god.get("catch_play"))},
            "r": list(river or []),
            # 2026-09-18 诊断：四家副露牌面计数（可见张数三要素之一，另两个是手牌与河）。
            # 用于离线核对 view["all_melds"] 是否真的完整（对照门户重建）。
            "am": [[t for m in (seat_melds or [])
                    for t in ((m.get("tiles") if isinstance(m, dict) else None)
                              or ([m.get("tile")] * (4 if m.get("type") == "gang" else 3)
                                  if isinstance(m, dict) and m.get("tile") else []))]
                   for seat_melds in (view.get("all_melds") or [])],
            "a": act, "ms": round(float(ms or 0), 1),
            "age_ms": (None if age_ms is None else round(float(age_ms), 1)),
            "rnd": (None if rnd is None else int(rnd))}


def _act_key(a):
    """动作比较键（用于影子一致性统计）。"""
    if not isinstance(a, dict):
        return None
    return (str(a.get("action") or ""), str(a.get("tile") or ""))


def _hand13_for_compare(snap_or_view):
    """把（可能含刚摸牌的）手牌规范化到 13 张形态，供"缓存 vs 新鲜"同表征比较。"""
    h = list((snap_or_view or {}).get("my_hand") or [])
    dt = (snap_or_view or {}).get("drawn_tile") or ""
    melds = (snap_or_view or {}).get("melds") or []
    try:
        need = 13 - 3 * len(melds)
    except Exception:
        need = 13
    if dt and len(h) == need + 1:
        try:
            h.remove(dt)
        except ValueError:
            pass
    return sorted(h)


def _can_claim_locally(hand, tile, kind, my_seat, from_seat):
    """本地（用缓存手牌）判断这个弃牌是否**可能**给我方碰/吃/杠窗口。"""
    if not tile or not hand:
        return False
    if kind == "peng":
        return list(hand).count(tile) >= 2
    if my_seat is None or from_seat is None or (int(my_seat) - int(from_seat)) % 4 != 1:
        return False
    if len(tile) < 2 or tile[-1] not in "wbt":
        return False
    try:
        n = int(tile[0])
    except ValueError:
        return False
    suit = tile[-1]
    h = list(hand)
    for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
        if 1 <= a <= 9 and 1 <= b <= 9 and \
                ("%d%s" % (a, suit)) in h and ("%d%s" % (b, suit)) in h:
            return True
    return False


def _needs_snapshot(events, my_hand=None, my_seat=None):
    """这批事件是否需要再拉一次全量快照。

    R1113 修订（重要）：**不要**用"本地看得出来才取快照"来省调用。
    服务端在弃牌瞬间可能尚未把我们的座位写进 `responding_seats`（hybrid 实验实测
    `response_seat_not_listed` 762 次），旧代码正是靠后续 `pass/timeout` 批次的
    快照"再看一眼"才捕获到吃/碰窗口。R1092/R1098 跳过这些批次后，
    实测 **我们看到的 response_chi 决策行 49.5 → 34.0/块（-31%）、吃的实现 4.36 → 2.2/文件**。
    因此：这里的规则只做"明显无关"的判定，窗口捕获依靠调用方的 `window_watch`。
    """
    for ev in events or []:
        t = ev.get("type")
        if t == "tile_discarded":
            return True                      # 可能出现碰/吃/杠窗口
        if t == "tile_drawn" and ev.get("tile"):
            return True                      # 本人摸牌（牌面仅自己可见）
        if t in ("peng", "chi", "gang"):
            return True                      # 公开副露变化
        if t in ("round_ended", "finished", "stage_done", "stage_open"):
            return True                      # 局末/场末/阶段切换
    return False


def _end_reason(res, snap):
    """场次是否结束及原因：响应的 finished 标记 / 快照 phase==finished。"""
    if res.get("finished"):
        return "finished 标记"
    if snap is not None and snap.get("phase") == "finished":
        return "phase=finished"
    return None


def play_game(client, gid, strategy, recorder=None):
    """打一场：返回该场结束时快照（含 scores），或 None（异常中止由调用方决定）。

    recorder（可选 ReplayRecorder）：每批增量事件回调 on_event(gid, ev)，
    场次结束回调 close_game(gid) 落盘该场事件流。

    事件等待：优先 /api/games/{id}/notify SSE（v12+，不占 /state 额度——
    M 并发下长轮询会撞 16/s 聚合限速致窗口 409 风暴）；notify 断连/禁用
    （HM_NO_NOTIFY=1）时回退传统 30s 长轮询（语义完全同旧版）。
    """
    seq = 0
    pending_count = 0           # 连续长挂起计数（防漏窗口兜底）
    shape_retry = 0             # 形态冲突连续全量重建次数（防死循环）
    last_window_key = None      # 最近已响应的窗口键 (phase, turn)
    decided_seq_sig = None      # 非窗口最近已决策的 (phase, seq) —— 防 409 死循环
    # 新局开头盲区的有界主动短轮询截止（见 R438）。
    # ⚠2026-09-18 两次尝试的历史：
    #   ① 只在 round_ended 后开 watch ⇒ 第 2~8 局 0/51 完美，但**第 1 局 7/9=77.8% 被代打**；
    #   ② 开局也开 12s watch ⇒ 第 1 局降到 0.85%，**但整体从 0.57% 升到 1.4~2.2%**：
    #      10 局同时轮询 ≈10 req/s 打满共享 /state 桶（12/s），反而拖慢真正该出手的时刻。
    # ③ 开局开 3s 短窗 + 按座位错峰间隔（见下方 sleep）⇒ 实测整体 0.29%/0.66% ✅。
    # ④ 2026-09-18 第三次尝试再加长到 6s（R500）⇒ **两房整体 1.83%/2.07%，且第 1 局仍 4/7=57%**
    #    ⇒ 与 ② 同一失败签名（窗口越长、总请求越多 ⇒ 共享 /state 桶被摊薄）⇒ **R503 已回退到 3s**。
    #    **结论：第 1 局缺口不是"窗口不够长"能解决的**，不要再改这个数；按 R498/§15 当**监控项**处理。
    open_watch_until = time.monotonic() + 3.0
    open_watch_n = 0            # 每次 watch 内已打印的快照数（探针，限量）
    my_seat = -1                # 本人座位（用于判断下一局庄家是不是我）
    self_drawn = ""             # 最近一次本人摸牌（tile_drawn 事件，tile 仅自己可见）
    self_replenish = False      # 该次本人摸牌是否为自杠后补牌（gang_replenish
                                # ——服务器已将该补牌并入快照 my_hand）
    self_gang_tiles = []        # 本局在 draw 回合自杠的牌面集合（暗杠/补杠）——
                                # 每次成功自杠后整个 round 服务器 my_hand 恒多计该杠组
                                # 第 4 张（round 级幻影），逐张抽掉；下局 round_ended 清空。
                                # 同局多次不同自杠各自 +1，故用集合+逐个移除（非单标量）。
                                # （T6 P0 实测：不只补牌即刻，整个 round 摸牌回合皆然）
    self_offer = None           # 最近弃牌 (tile, seat)（tile_discarded 事件，公开）
    river = []                  # 当前局公开弃牌河（round_ended 清空）
    dealer = None               # 当前局庄家；首局由首个无摸牌弃牌推断，后续由 round_ended 续推
    round_draw_seats = set()    # 本局已出现摸牌事件的座位（用于推断首局庄家）
    round_no_local = 0           # 诊断用：本地轮次计数（R1066）
    window_age_t0 = None
    window_age_ms = None
    tracker = MeldTracker()     # 本人副露跟踪（真机快照无 melds，本地累计）
    notifier = None
    if os.environ.get("HM_NO_NOTIFY") != "1":
        try:
            from .notify import NotifyLine
            notifier = NotifyLine(client, gid)
            notifier.start()
        except Exception:
            notifier = None     # 构造失败 → 长轮询
    last_res_kind = "?"         # 探针：最近一次循环响应的形态
    # R1092 诊断：/state 调用计数与"跳过无关快照"次数（零行为变更，仅计数）
    state_calls = [0]
    events_seen = [0]
    snap_skipped = [0]
    window_watch = 0            # R1113：弃牌后"再看几批"（捕获延迟登记的响应窗口）
    snap_evt_stall = 0          # R1095：连续拿到"快照+事件"却不消费事件的次数（防活锁）
    last_hand = None            # R1098：最近一次成功快照的本人暗牌（用于本地窗口预判）
    last_melds = None           # R1101：最近一次成功快照的四家副露（诊断缓存新鲜度）
    last_drawn = ""             # R1101b：缓存刚摸牌（同表征比较用）
    last_snap_raw = None        # R1106：最近一次成功快照（原始 dict）
    cw_used = [0]; cw_fallback = [0]
    # R1106 开关：哨兵文件 var/.cached_window（或 env HM_CACHED_WINDOW=1）——
    # 默认关闭；开启后窗口决策不再拉第二次全量快照（用缓存手牌/副露合成视图）。
    _cw_flag = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "var", ".cached_window")
    cached_window = (os.environ.get("HM_CACHED_WINDOW") == "1"
                     or os.path.exists(_cw_flag))
    snap_evt_seen = [0]         # 诊断：响应同时带快照+事件的次数
    # R1101 诊断：窗口时刻"缓存手牌/他家副露 是否等于新鲜快照"（验证 R1100 的缓存决策方案）
    cmp_n = [0]; cmp_hand_same = [0]; cmp_meld_same = [0]
    cmp_dec_n = [0]; cmp_dec_same = [0]   # R1105：动作级影子（缓存手牌/副露 vs 新鲜快照）
    snap_evt_held = [0]         # 诊断：其中被"暂不推进水位"拦下的次数（河相关）
    # 2026-09-10 /state 预算优化：实测自动房 10 场并发下每个决策要拉 2 次
    # /state（增量事件 + seq=0 全量快照），令牌桶排队 625ms×2 ≈ 1.25s，超过
    # 1s 响应窗口 → 吃 67%/碰 78% 被 409 拒（1109 次失败 claim 中 66% 那张牌
    # 最终无人要，即我方迟到）。notify 已推水位信号，而全量快照自带
    # my_hand/melds/drawn_tile/last_discard/responding_seats，足以自足决策
    # → 直接拉快照，省掉增量事件那一跳，/state 需求减半。
    # HM_FAST_STATE=0 可退回旧的两跳路径。
    # 2026-09-10 实测（房 a_fb0a32b036e5）：fast_state 开启虽再把 /state 需求
    # 压低，但快照并非每条路径都带 drawn_tile → 44 次事件兜底 + 24 次手牌形态
    # 不一致，discard 409 率 0%→14.5%（= 服务器代打，直接丢分）→ **默认关闭**，
    # 仅留 HM_FAST_STATE=1 供后续在「快照必带 drawn_tile」验证后重开。
    fast_state = os.environ.get("HM_FAST_STATE") == "1"
    # R1068/R1069 自适应混合：先拉 seq=0 快照，字段不足才补拉增量（优先于 fast_state）。
    # 开关：环境变量 HM_HYBRID_STATE=1 **或** 哨兵文件 var/.hybrid_state
    # （哨兵文件与 .official_mode 同约定：自愈链重启进程时环境变量会丢，文件不会）。
    _hybrid_flag = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "var", ".hybrid_state")
    hybrid_state = (os.environ.get("HM_HYBRID_STATE") == "1"
                    or os.path.exists(_hybrid_flag))

    def _state(seqv, tries=3):
        """带瞬断重试的 /state：429/5xx/网络不得直接打死整场线程。

        2026-09-10 实测：未保护时一次 429 就 raise 出 play_game → 线程退出 →
        该场 80 局全丢（房 a_fb0a32b036e5 有 4 场如此终止）。
        """
        last = None
        for i in range(tries):
            try:
                state_calls[0] += 1
                return client.game_state(gid, seqv)
            except ApiError as e:
                last = e
                if e.status in (0, 429) or (e.status and e.status >= 500):
                    time.sleep(0.6 * (i + 1))
                    continue
                raise
        raise last

    ev_seq = seq                  # 事件水位（仅快照缺 drawn_tile 时兜底补拉）
    fast_fallback = 0
    while True:
        if time.monotonic() < open_watch_until:
            # 新局开头盲区（2026-09-18 定位）：除"庄家开局首弃"外，本桌每个动作
            # 前面都有一条 `tile_drawn` 事件能把我们唤醒；而庄家首弃是**新局第一个
            # 动作、前面没有任何事件** ⇒ 事件驱动的我们只能干等长轮询（服务端最长挂
            # 30s），而出牌窗口只有 3s ⇒ 实测 48% 被服务端代打（top32 9.35%，且
            # 09-10 我们本是 9.2%，09-12 起回归）。这里在新局开头做**有界**（2.5s、
            # 间隔 0.25s）立即快照轮询，主动把"轮到我"的状态取回来。
            try:
                res = _state(0)
            except Exception as e:      # 绝不因新路径异常弄死整场线程
                log("open-watch 取态异常(%s)，回退长轮询", type(e).__name__)
                open_watch_until = 0.0
                res = _state(seq)
            _s = res.get("snapshot") or {}
            _ph = _s.get("phase") or ""
            if open_watch_n < 4 and _ph != "settled":
                open_watch_n += 1
                log("[openwatch] n=%d phase=%s turn=%s seat=%s my_hand=%d "
                    "drawn=%r", open_watch_n, _ph, _s.get("turn"),
                    _s.get("seat"), len(_s.get("my_hand") or []),
                    _s.get("drawn_tile"))
            # ★2026-09-18 更正停止条件：**只有"轮到本人可动作"才结束 watch**。
            # 旧条件 `_ph != "settled"` 在**开局第 1 局**会立刻误停（开局时 phase 就是
            # draw/response_* 但 turn 是别人）⇒ 实测某房 10 局里 5 局的第 1 局首弃被代打。
            _seats = _s.get("seat")
            _mine = ((_ph == "draw" and _s.get("turn") == _seats) or
                     (_ph.startswith("response_") and
                      _seats in (_s.get("responding_seats") or [])))
            if _mine:
                open_watch_until = 0.0
            else:
                # ★2026-09-18：**按座位错峰**的轮询间隔（seat 0..3 → 0.3/0.6/0.9/1.2s）。
                # 10 局同时开局时，若都用同一间隔会同步成 ~10 req/s 打满共享 /state 桶（12/s）；
                # 错峰后同一时刻只有约 1/4 的局在发请求 ⇒ 既覆盖第 1 局、又不挤占别人。
                _d = 0.3 * (1 + (_seats % 4 if isinstance(_seats, int) and _seats >= 0 else 2))
                time.sleep(_d)
        elif notifier is not None and not notifier.down:
            ev = notifier.wait_event(timeout=33.0)
            ev = notifier.drain(ev)      # 合并积压帧：一次 fetch 覆盖全部
            if ev == "down":
                # notify 断连：该场回退传统长轮询（语义与旧版一致）
                res = _state(seq)
            elif ev == "event":
                if hybrid_state:
                    # ① 只拉快照（省掉增量那一跳）；② 字段不足才补拉增量
                    res = _state(0)
                    try:
                        from .faststate import snapshot_covers
                        _ok, _why = snapshot_covers(res.get("snapshot") or {})
                    except Exception:
                        _ok, _why = False, "pred_err"
                    if not _ok:
                        _sn = res.get("snapshot") or {}
                        log("[hybrid] 快照不足(%s) phase=%s seat=%s turn=%s rs=%s ld=%r dt=%r",
                            _why, _sn.get("phase"), _sn.get("seat"), _sn.get("turn"),
                            _sn.get("responding_seats"), _sn.get("last_discard"),
                            _sn.get("drawn_tile"))
                        _res2 = _state(seq)
                        if _res2.get("events") or _res2.get("snapshot"):
                            res = _res2
                elif fast_state:
                    res = _state(0)   # 全量快照（单跳；历史上造成 14.5% discard 409，默认关闭）
                else:
                    res = _state(seq)  # 帧后拉增量（本地水位）
            else:
                # keepalive/timeout：30s 无新事件 → 仍按旧版节奏做一次挂起
                # state（跨局发牌/漏帧等"无事件推进"靠它发现；挂起至多 30s
                # 返回 pending）。notify 只负责把事件到达提前，不改变兜底语义。
                res = _state(seq)
        else:
            res = _state(seq)
        last_res_kind = "events" if res.get("events") else \
            ("snap" if res.get("snapshot") else
             ("pend" if res.get("pending") else "fin"))
        snap = res.get("snapshot")

        reason = _end_reason(res, snap)
        if reason:
            # 场终批可能携带 round_ended 等收尾事件——先喂 recorder 再退出
            # （2026-09-09 实测：此批被短路导致录制事件缺 round_ended，
            #   逐局结果/语料不完整）
            for ev in res.get("events") or []:
                if recorder:
                    recorder.on_event(gid, ev)
            log("本场结束: %s（gid=%s）", reason, gid)
            log("[state-budget] gid=%s state_calls=%d events=%d snap_skipped=%d "
                "calls_per_event=%.2f snap_evt_seen=%d snap_evt_held=%d "
                "cache_cmp=%d hand_same=%.3f meld_same=%.3f dec_cmp=%d dec_same=%.3f cw_used=%d cw_fb=%d",
                gid, state_calls[0], events_seen[0], snap_skipped[0],
                float(state_calls[0]) / max(1, events_seen[0]),
                snap_evt_seen[0], snap_evt_held[0], cmp_n[0],
                (float(cmp_hand_same[0]) / cmp_n[0]) if cmp_n[0] else -1.0,
                (float(cmp_meld_same[0]) / cmp_n[0]) if cmp_n[0] else -1.0,
                cmp_dec_n[0],
                (float(cmp_dec_same[0]) / cmp_dec_n[0]) if cmp_dec_n[0] else -1.0,
                cw_used[0], cw_fallback[0])
            if recorder:
                recorder.close_game(gid)
            if snap and snap.get("scores") is not None:
                seat = snap.get("seat", -1)
                scores = snap.get("scores")
                log("本场积分 seat=%d: %s", seat, scores)
                if seat is not None and 0 <= seat < len(scores):
                    log("我的本场得分: %s", scores[seat])
            return snap

        if res.get("pending"):
            # 30s 内无新事件：继续挂起；连续两次 pending 做一次全量重建兜底
            # （防「只更新快照不发事件」的窗口/换庄等被挂起错过）
            pending_count += 1
            if pending_count >= 2:
                pending_count = 0
                seq = 0
            continue

        if snap is None:
            # 增量事件：解析本人摸牌与弃牌 offer/river（快照不含敏感牌面：
            # tile_drawn 仅自己可见；窗口 offer = 最近 tile_discarded.tile），
            # 推进 seq 后重建权威快照再决策。
            events_seen[0] += len(res.get("events") or [])
            for ev in res.get("events") or []:
                if recorder:
                    recorder.on_event(gid, ev)
                seq = max(seq, int(ev.get("seq", seq)))
                ev_seq = max(ev_seq, int(ev.get("seq", ev_seq)))
                etype = ev.get("type")
                if etype == "round_ended":
                    round_no_local += 1
                    data = ev.get("data") or {}
                    old_dealer = data.get("dealer")
                    winner = ev.get("seat")
                    if old_dealer is not None:
                        # 与模拟器/平台一致：庄胡则连庄，闲胡则胡牌者接庄。
                        dealer = old_dealer if winner is None or winner == old_dealer else winner
                    river = []          # 新局开始：弃牌河清空
                    round_draw_seats = set()
                    tracker.reset()     # 新局：副露清零（跨局残留曾致整局误判）
                    self_drawn = ""
                    self_replenish = False
                    self_gang_tiles = []    # 新局：自杠 round 级幻影集合清空
                    self_offer = None
                    last_window_key = None  # 跨局相同 (phase,turn,offer) 不得误去重
                    # 新局：开一段有界主动短轮询，覆盖"庄家首弃前面没有事件"的盲区。
                    # 只在**下一局庄家是自己**时才开（新局第一个动作才是我们的），
                    # 省掉 3/4 的无谓轮询；12s 上限覆盖实测 0~8s 的结算空档
                    #（中位 5s、20% 恰好 8s，见 R443）。
                    if dealer is not None and dealer == my_seat:
                        open_watch_until = time.monotonic() + 12.0
                        open_watch_n = 0
                elif etype == "tile_drawn":
                    if ev.get("seat") is not None:
                        round_draw_seats.add(ev["seat"])
                    if ev.get("tile"):
                        self_drawn = ev["tile"]     # 非空 tile = 本人刚摸
                        # 杠补牌：服务器把该牌并入快照 my_hand（标记后续按"去补"处理）
                        self_replenish = bool((ev.get("data") or {}).get(
                            "gang_replenish"))
                elif etype == "tile_discarded" and ev.get("tile"):
                    if dealer is None and ev.get("seat") is not None and \
                            ev.get("seat") not in round_draw_seats:
                        dealer = ev.get("seat")   # 首局庄家首弃（无前置摸牌）
                    self_offer = (ev["tile"], ev.get("seat"))   # 弃牌牌面（公开）
                    window_age_t0 = time.perf_counter()          # 仅用于 age_ms 诊断
                    river.append(ev["tile"])
                    window_watch = 6      # R1113：接下来 6 批必须取快照（窗口捕获优先）
                elif etype in ("chi", "peng", "gang") and ev.get("tile"):
                    # R1095：该牌被副露拿走 ⇒ 从本地河移除（river_fidelity 的"扣吃碰口径"）。
                    # 暗杠不是从河里拿的（补杠同理）⇒ 只在明杠/碰/吃时移除，避免误删同牌弃张。
                    _kind = (ev.get("data") or {}).get("kind")
                    if not (etype == "gang" and _kind == "an"):
                        try:
                            river.remove(ev["tile"])
                        except ValueError:
                            pass
                    # R1104：同步维护"缓存的四家副露"（副露事件本来就收得到），
                    # 供缓存窗口决策使用 ⇒ 让 meld_same 从 0.84-0.93 逼近 1.0。
                    try:
                        _seat = ev.get("seat")
                        if isinstance(_seat, int) and 0 <= _seat < 4 and \
                                isinstance(last_melds, list) and len(last_melds) == 4:
                            _tl = list((ev.get("data") or {}).get("tiles") or [])
                            if etype == "peng":
                                _tl = [ev["tile"]] * 3
                            elif etype == "gang":
                                _tl = [ev["tile"]] * 4
                            if etype == "gang" and _kind == "bu":
                                for _m in last_melds[_seat]:
                                    if _m.get("type") == "peng" and _m.get("tile") == ev["tile"]:
                                        _m["type"] = "gang"
                                        _m["tiles"] = [ev["tile"]] * 4
                                        break
                            elif _tl:
                                last_melds[_seat].append(
                                    {"type": etype, "tile": ev["tile"], "tiles": _tl})
                    except Exception:
                        pass
            # 2026-09-18：曾在此处试过 round_ended 后 seq=0 强制重同步，两场读数
            # 无法与"本机重负载"分离（同窗另跑全量测试/审计）⇒ 已回退，等 v2 探针
            # + 干净样本再定；探针本身行为中性，保留。
            # R1092：无关事件（他人摸牌/他人 pass/timeout）不再白拉一次全量快照。
            if window_watch > 0:
                window_watch -= 1
            elif not _needs_snapshot(res.get("events") or []):
                snap_skipped[0] += 1
                pending_count = 0
                continue
            # R1106：缓存窗口决策——事件提供窗口上下文、缓存提供我方手牌/副露，省掉
            # 第二次 /state（迟到 409 的 age_ms p50=643ms 全部来自那次排队）。
            # 保守条件：只有"碰/吃二选一"才走；两种都可能（相位歧义）或无缓存 ⇒ 回退拉快照。
            _synth = None
            if cached_window and last_hand is not None and last_melds is not None \
                    and last_snap_raw is not None and isinstance(my_seat, int) and my_seat >= 0:
                _my_melds = (last_melds[my_seat] if isinstance(last_melds, list)
                             and len(last_melds) == 4 else [])
                _evs_cw = list(res.get("events") or [])
                # R1106b：同一批里"被别人碰/吃/杠抢走"的弃牌 ⇒ 窗口已关闭，绝不合成。
                # 漏掉这条会造成"凭空合成窗口 → 立即提交 → 服务端 INVALID_ACTION"，
                # 实测一次上线即产生 78 条 response_chi 409（age_ms=0）。
                _sup_idx = set()
                for _i2, _e2 in enumerate(_evs_cw):
                    if _e2.get("type") in ("chi", "peng", "gang") and _e2.get("tile"):
                        for _j2 in range(_i2 - 1, -1, -1):
                            _e3 = _evs_cw[_j2]
                            if _e3.get("type") == "tile_discarded" and _e3.get("tile") == _e2.get("tile"):
                                _sup_idx.add(_j2)
                                break
                for _i, _e in enumerate(_evs_cw):
                    if _e.get("type") != "tile_discarded" or not _e.get("tile"):
                        continue
                    if _i in _sup_idx:
                        continue          # 被抢走 ⇒ 跳过
                    _synth = None         # R1106d：批内多个弃牌 ⇒ 只认最后一个（更早窗口可能已关闭）
                    _t = _e["tile"]; _s = _e.get("seat")
                    _cp = _can_claim_locally(last_hand, _t, "peng", my_seat, _s)
                    _cc = _can_claim_locally(last_hand, _t, "chi", my_seat, _s)
                    # R1106c：**只对碰窗口**启用缓存决策。
                    # 依据：① 碰窗口构造上独占（2 张在我手 + 1 张被打出 ⇒ 他人最多 1 张，无法抢；
                    #       历史实测 1343/1343 = 100% 独占）；② 迟到 409 全部是 response_peng。
                    # 吃的相位歧义实测会造成大量 INVALID_ACTION（一次上线 78 条 response_chi 409，age_ms=0），
                    # 因此吃一律回退到"拉快照"的安全路径。
                    _kind = "peng" if (_cp and not _cc) else None
                    if _kind:
                        _synth = dict(last_snap_raw)
                        _synth["phase"] = "response_" + _kind
                        _synth["turn"] = _s
                        _synth["responding_seats"] = [my_seat]
                        _synth["last_discard"] = _t
                        _synth["my_hand"] = _hand13_for_compare(
                            {"my_hand": list(last_hand), "drawn_tile": last_drawn,
                             "melds": _my_melds})
                        _synth["melds"] = last_melds
                        _synth["drawn_tile"] = ""
            if _synth is not None:
                snap = _synth
                cw_used[0] += 1
            else:
                cw_fallback[0] += 1
                auth = _state(0)
                snap = auth.get("snapshot")
                if snap is None:
                    continue
            # 2026-09-18 修复：**不要把水位推到快照的 seq**。
            # 原写法 `seq = max(seq, auth["seq"])` 会把"本批事件处理完"与"再拉一次
            # 全量快照"这两次请求**之间**到达的事件永久跳过 —— 实测 bot 的弃牌河
            # 每局开头就少 1 张、随局累积到少 9 张（扣掉吃碰后仍差），而河是所有
            # real_ukeire 活张数的输入 ⇒ 活张数系统性高估、弃牌选择偏离最优。
            # 保持水位 = 最后一条已处理事件，下一次 /state 会把漏掉的事件补回来。
        else:
            # R1095：响应**同时带快照与事件**时，旧实现直接推进水位、整批事件被丢弃
            # ⇒ round_ended（river=[]）与 tile_discarded（append）都丢 ⇒ 河跨局累积
            #   （全役 53.6 万决策实测：比权威原始口径平均多 13.35 张）。
            # 这里改为：有事件时不推进水位，让下一轮走增量路径把它们消费掉；
            # 连续 3 次仍如此（服务端持续返回快照+事件）才强制推进，避免活锁。
            _evs2 = res.get("events") or []
            _river_rel = any(e.get("type") in ("round_ended", "tile_discarded",
                                               "chi", "peng", "gang") for e in _evs2)
            if _evs2:
                snap_evt_seen[0] += 1
            if _river_rel and snap_evt_stall < 3:
                snap_evt_held[0] += 1
                snap_evt_stall += 1
            else:
                snap_evt_stall = 0
                seq = int(res.get("seq", seq))

        prev_hand = last_hand          # R1105：影子比较用的"缓存侧"（刷新前）
        prev_melds = last_melds
        prev_drawn = last_drawn
        view = snap_view(snap)
        my_seat = view.get("seat", -1)
        # R1101：若本批含弃牌（= 可能有窗口），比较"缓存手牌/他家副露"与新鲜快照
        if any(e.get("type") == "tile_discarded" for e in (res.get("events") or [])):
            if last_hand is not None:
                cmp_n[0] += 1
                if _hand13_for_compare(view) == _hand13_for_compare({"my_hand": last_hand, "drawn_tile": last_drawn, "melds": view.get("melds") or []}):
                    cmp_hand_same[0] += 1
                if str(view.get("all_melds") or []) == str(last_melds):
                    cmp_meld_same[0] += 1
        last_hand = list(view.get("my_hand") or []) or None   # R1098：刷新缓存手牌
        last_snap_raw = snap                                   # R1106：缓存原始快照（合成窗口视图用）
        last_drawn = view.get("drawn_tile") or ""              # R1101b：缓存刚摸牌（用于同表征比较）
        last_melds = view.get("all_melds") or []               # R1101：缓存他家副露
        # 牌墙深度的廉价代理：本局公开弃牌总数（每次弃牌≈一次摸牌）。
        # 供「最后 10 墩禁止杠」做保守前置判断（服务端才是权威，见 bot/speedtugc.py 注释）。
        try:
            view["river_len"] = len(river)
        except Exception:
            pass
        # 副露权威源（v24 适配 2026-09-08）：服务器快照自带 melds 数组时直接
        # 采用（tracker 与服务器在窗口竞态下会分叉——自动房实测 tracker 多记
        # 一组致 guard 风暴）；仅字段缺失（旧版/观赛）时退回本地 tracker。
        if not view.pop("_snap_has_melds", False):
            view.update(tracker.view_extra())   # 注入本人副露（兜底路径）
        view["river"] = list(river)         # 注入公开弃牌河（SpeedG 已见扣减用）
        if view.get("dealer") is None:
            view["dealer"] = dealer          # C063：注入当前庄家（赔付评估）
        if view["seat"] < 0:
            continue            # 观赛视角无动作权

        # 窗口 offer 注入：快照无 offer_tile（敏感牌面仅事件流公开）——
        # 窗口期（response_*）若事件流给出弃牌牌面，则补入 view
        if self_offer is not None:
            offer_tile, offer_seat = self_offer
            if view["phase"].startswith("response_") and \
                    view.get("turn") == offer_seat:
                view["offer_tile"] = offer_tile
        # v24 兜底（2026-09-09 实测）：409/重建等路径下 tile_discarded 事件
        # 可能缺失 → self_offer 注入失效（自动房 61% 窗口 offer 缺失致副露被
        # 系统性压制）。窗口必由 turn 座弃牌触发 → 快照 last_discard 即该弃牌。
        if view["phase"].startswith("response_") and \
                not view.get("offer_tile"):
            ld = snap.get("last_discard") if snap is not None else None
            if isinstance(ld, str) and ld:
                view["offer_tile"] = ld
        # 本人出牌后清掉过期 offer（同弃牌不重复评估）
        if self_offer is not None and view["phase"] == "draw" and \
                view.get("turn") == view["seat"]:
            self_offer = None

        # 真机手牌语义：权威快照 my_hand 恒为「不含刚摸牌」的 13-3e-g 张，
        # 本人摸牌只经 tile_drawn 事件（tile 仅对自己可见）传达 → 把最近一次
        # 本人摸牌并入 view，策略才能判胡/算向听（引擎视角 = 摸后 14 张）。
        drawn_tile = view.get("drawn_tile") or ""
        if fast_state and not drawn_tile and \
                view["phase"] == "draw" and view.get("turn") == view.get("seat"):
            # 罕见兜底：快照未附刚摸牌 → 补拉一次增量事件（正常路径不触发）
            fast_fallback += 1
            try:
                inc = client.game_state(gid, ev_seq)
                for ev2 in inc.get("events") or []:
                    if recorder:
                        recorder.on_event(gid, ev2)
                    ev_seq = max(ev_seq, int(ev2.get("seq", ev_seq)))
                    if ev2.get("type") == "tile_drawn" and ev2.get("tile"):
                        self_drawn = ev2["tile"]
                    elif ev2.get("type") == "tile_discarded" and ev2.get("tile"):
                        self_offer = (ev2["tile"], ev2.get("seat"))
                        river.append(ev2["tile"])
                log("[faststate] 快照缺刚摸牌 → 事件兜底 #%d", fast_fallback)
            except ApiError:
                pass
            drawn_tile = view.get("drawn_tile") or self_drawn
        if not drawn_tile and self_drawn:
            drawn_tile = self_drawn
        if drawn_tile and view["phase"] == "draw" and \
                view["turn"] == view["seat"]:
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            expect_hold = 14 - 3 * exposed - gangs      # 摸后应有张数
            # 服务器快照语义：普通摸牌为不含刚摸，张数 = expect-1，判胡前补回
            # 刚摸变 expect；副露后部分路径快照已含刚摸（=expect）直接可用。
            # 自杠（暗杠/补杠）当局特殊：每次成功自杠后，该杠组第 4 张在快照
            # 私有张内恒多计一次（round 级幻影，不只补牌即刻，整个 round 摸牌
            # 回合皆然——真机/探针 p0g 同签名），同局多杠各自 +1。此幻影须每
            # 回合按「本局自杠牌面集合」逐张抽掉（多杠逐张抽幻影）；集合内无一
            # 在手仍超长则落下方跳过守卫（once 旧标量实现两轮后 len 恒 >expect
            # 直接终局之根因，改集合式修复自杠静默停摆）。
            while len(hand) > expect_hold and self_gang_tiles:
                # 自杠幻影优先治：本局有挂过自杠且手牌仍超 expect → 尝试找仍在
                # hand 的本局自杠牌面（按集合序）逐个移除，退回合法长度。
                found = False
                for t in self_gang_tiles:
                    if t in hand:
                        hand.remove(t)      # 抽掉 1 个该杠牌实例
                        found = True
                        log("自杠当局核对: 抽杠牌 %s 后 len=%d expect=%d e=%d g=%d",
                            t, len(hand), expect_hold, exposed, gangs)
                        break
                if not found:
                    break       # 无任何杠面在手仍超 → 无可抽，交下方守卫
            # 服务端 melds 偶发滞后：my_hand 已经反映副露扣牌，但 melds 仍为空，
            # 会让 expect_hold 多 3 张。若本地 tracker 的 e/g 与手牌长度完全一致，
            # 采用 tracker 的副露视图继续出牌，不能跳过本回合（实测 11/11 自洽）。
            if len(hand) != expect_hold:
                te, tg = tracker.exposed(), tracker.gangs()
                local_hold = 14 - 3 * te - tg
                if (te, tg) != (exposed, gangs) and len(hand) == local_hold:
                    log("采用本地副露计数: len=%d local_e=%d local_g=%d srv_e=%d srv_g=%d",
                        len(hand), te, tg, exposed, gangs)
                    view["melds"] = tracker.view_extra()["melds"]
                    exposed, gangs = te, tg
                    expect_hold = local_hold
            # 若服务端 melds 持续为空/滞后、tracker 也无法解释，但手牌比
            # 期望少 3/4 张，按缺失牌数反推一个与长度自洽的副露视图：
            # 3e+g = 14-len(hand)。这不伪造牌，只让策略能对真实手牌出牌。
            if len(hand) != expect_hold and len(hand) < expect_hold:
                cost = expect_hold - len(hand)
                if 3 <= cost <= 8:
                    g_inf = cost % 3
                    e_inf = (cost - g_inf) // 3
                    inferred = ([{"type": "gang", "tile": ""}] * g_inf +
                                [{"type": "peng", "tile": ""}] * e_inf)
                    log("手牌长度反推副露: len=%d e=%d g=%d (原 e=%d g=%d)",
                        len(hand), e_inf, g_inf, exposed, gangs)
                    view["melds"] = inferred
                    exposed, gangs = e_inf, g_inf
                    expect_hold = 14 - 3 * e_inf - g_inf
            if len(hand) == expect_hold:
                # 长度已对齐 expect（可能经自杠逐张抽除，或原本就含刚摸）：与已
                # 计入 e/g 的杠组一致，交策略正常决策（仍留 drawn_tile 供判杠上/弃牌）。
                view["my_hand"] = hand
                shape_retry = 0
                if self_gang_tiles:
                    log("自杠当局核对完成: len=%d expect=%d —— 继续决策",
                        len(hand), expect_hold)
            elif len(hand) == expect_hold - 1 and drawn_tile and \
                    drawn_tile not in hand:
                hand.append(drawn_tile)      # 不含 → 补第 N 张
                view["my_hand"] = hand
                view["drawn_tile"] = drawn_tile
            elif self_replenish and len(hand) == expect_hold + 1:
                # 杠补牌即刻且杠牌实例已不在手（刚补完快照误并）→ 退掉补牌回
                # expect（旧 T5b 逻辑兜底）；仍留 drawn_tile 供判杠上/弃补牌。
                if drawn_tile and drawn_tile in hand:
                    hand.remove(drawn_tile)
                else:
                    hand.pop()
                view["my_hand"] = hand
                view["drawn_tile"] = drawn_tile or ""
                log("自杠补牌核对: 退补牌后 len=%d expect=%d e=%d g=%d —— 继续决策",
                    len(hand), expect_hold, exposed, gangs)
            elif len(hand) != expect_hold:
                # claim 后（非自杠局面）服务器瞬时仍回「扣减前」旧手牌（len 偏大、
                # 与已 +1 的副露数冲突）→ 本轮放弃出牌，等事件推进同步；
                # 若正处于窗口期，先标记已响应防重复提交（409 风暴源）
                log("手牌形态暂不一致 len=%d expect=%d e=%d g=%d —— 跳过本轮",
                    len(hand), expect_hold, exposed, gangs)
                log("  [debug] res=%s seq=%d drawn_tile=%r self_drawn=%r "
                    "snap_hand=%s", last_res_kind, seq, drawn_tile,
                    self_drawn, ",".join(sorted(hand)))
                log("  [debug] self_gang_tiles=%s self_replenish=%r",
                    self_gang_tiles, self_replenish)
                if os.environ.get("HM_SNAPDEBUG"):
                    # 根因探针：拉服务器权威快照，对照 melds/长度与本地 tracker
                    try:
                        auth = client.game_state(gid, 0)
                        a_snap = auth.get("snapshot") or {}
                        log("  [snapdebug] srv_len=%d srv_melds=%s srv_drawn=%r",
                            len(a_snap.get("my_hand") or []),
                            json.dumps(a_snap.get("melds") or [],
                                       ensure_ascii=False)[:200],
                            a_snap.get("drawn_tile"))
                    except Exception:
                        pass
                # 形态冲突先短重试全量重建；若同一冲突持续，改回等事件推进，
                # 避免服务端持续返回同一快照时形成无限请求循环。
                shape_retry += 1
                if shape_retry <= 2:
                    seq = 0
                    time.sleep(0.05)
                    continue
                log("形态冲突连续 %d 次，改等事件推进", shape_retry)
                time.sleep(0.30)
                continue

        # 窗口去重（真机语义）：同一窗口（phase+弃牌者 turn+弃牌牌面）只响应
        # 一次；窗口内其他玩家的响应会推进 seq 但窗口未关——重复 pass/claim
        # 会 409。弃牌牌面精确标识窗口（同一弃牌者多窗口不混淆）。
        phase = view["phase"]
        offer_t = view.get("offer_tile") or ""
        window_key = (phase, view["turn"], offer_t)
        if phase.startswith("response_"):
            if window_key == last_window_key:
                continue
        # 非窗口（draw/deal 等）：同 (phase, seq) 局面不重复决策，防 409 死循环
        sig = (phase, seq)
        if not phase.startswith("response_") and sig == decided_seq_sig:
            continue
        window_age_ms = (None if window_age_t0 is None
                         else (time.perf_counter() - window_age_t0) * 1000.0)
        t_dec0 = time.perf_counter()
        dr_exc = False
        try:
            act = strategy.decide(view)
            # R1105 影子：仅把"手牌/四家副露"换成缓存侧的副本再决策一次，
            # 精确隔离"缓存是否陈旧到会改变动作"这一唯一变量（零行为变更，不提交该动作）。
            try:
                if str(view.get("phase") or "").startswith("response_") and \
                        prev_hand is not None and isinstance(prev_melds, list):
                    alt = dict(view)
                    alt["my_hand"] = _hand13_for_compare(
                        {"my_hand": prev_hand, "drawn_tile": prev_drawn,
                         "melds": view.get("melds") or []})
                    alt["all_melds"] = prev_melds
                    alt_act = strategy.decide(alt)
                    cmp_dec_n[0] += 1
                    if _act_key(alt_act) == _act_key(act):
                        cmp_dec_same[0] += 1
            except Exception:
                pass
        except Exception as e:
            # 策略异常（真机边缘局面）→ 窗口 pass / 非窗口不动作（等超时兜底）
            log("策略异常(%s: %s)——按 pass/等待处理" % (type(e).__name__,
                                                    str(e)[:100]))
            dr_exc = True
            act = {"action": "pass", "tile": ""} if phase.startswith(
                "response_") else None
        dec_ms = round((time.perf_counter() - t_dec0) * 1000.0, 1)
        if dec_ms > 300:
            log("⚠ [dperf] decide %.0fms phase=%s turn=%s hand_len=%d act=%s",
                dec_ms, phase, view.get("turn"),
                len(view.get("my_hand") or []),
                (act or {}).get("action") if act else None)
        # 决策记录（执行验证底座）：真动作待提交后统一登记（避免同对象双写）；
        # act=None 仅在【本人可行动/慢决策/异常】时落 noop 行——纯观赛空轮询不产生数据。
        dr = None
        if recorder and act is not None:
            dr = _dr_payload(gid, view, seq, river, dec_ms, act,
                              age_ms=window_age_ms, rnd=round_no_local)
        elif recorder:
            # 2026-09-18：draw 阶段无动作也必须留证（庄家开局首弃 48% 被服务端
            # 代打，需要区分"没收到事件"vs"收到但 my_turn 判假"）。
            if my_turn(view) or window_pending(view) or dec_ms > 100 or \
                    dr_exc or phase == "draw":
                drp = _dr_payload(gid, view, seq, river, dec_ms, None,
                                 age_ms=window_age_ms, rnd=round_no_local)
                drp["sub"] = "noop"
                recorder.on_decision(gid, drp)
        # 通用分歧探针（HM_XLOG=1 且非基准策略）：同局面基准重决策，
        # 动作不同即记 [xlog]——执行验证：候选差异是否真实发生（离线可数）。
        if act is not None and phase == "draw" and not view.get("drawn_tile"):
            log("[opendiscard] my_hand=%d act=%s turn=%s",
                len(view.get("my_hand") or []), act, view.get("turn"))
        if act is not None and os.environ.get("HM_XLOG") == "1" and \
                strategy.__class__.__name__ != "SpeedE":
            try:
                from .speede import SpeedE
                base = SpeedE().decide(view)
                if base != act:
                    log("[xlog] base=%s mine=%s phase=%s turn=%s",
                        base, act, phase, view.get("turn"))
            except Exception:
                pass
        if act is not None and phase == "draw" and \
                os.environ.get("HM_TRACE_STATE") == "1":
            # 诊断探针（默认关闭，HM_TRACE_STATE=1 打开）：用于证伪/证实
            # "庄家开局弃牌到底有没有被我们打过"（见 R435/R438）。
            log("[drawact] seat=%s turn=%s my_hand=%d drawn=%r melds=%d act=%s",
                view.get("seat"), view.get("turn"),
                len(view.get("my_hand") or []), view.get("drawn_tile"),
                len(view.get("melds") or []),
                (act or {}).get("action"))
        if act is None:
            if view.get("turn") == view.get("seat") and view.get("seat", -1) >= 0:
                log("\u26a0 [noturn] phase=%s seat=%s turn=%s my_hand=%d drawn=%r "
                    "res=%s seq=%d dr_exc=%s melds=%d", phase, view.get("seat"),
                    view.get("turn"), len(view.get("my_hand") or []),
                    view.get("drawn_tile"), last_res_kind, seq, dr_exc,
                    len(view.get("melds") or []))
            continue

        log("提交:", act, "phase=%s turn=%s" % (phase, view["turn"]))
        if os.environ.get("HM_AUDIT") and act.get("action") != "pass":
            # 决策审计行：局面摘要 + 动作（离线重放 oracle 对比用）
            melds = tracker.view_extra().get("melds") or []
            log("[audit] gid=%s seat=%d phase=%s turn=%d hand=%s drawn=%s "
                "melds=%d act=%s", gid, view["seat"], phase, view["turn"],
                ",".join(sorted(view["my_hand"])), view.get("drawn_tile") or "",
                len(melds), act.get("action") +
                (":" + act.get("tile", "") if act.get("action") != "pass" else ""))
        sub = None
        sub_ms = None
        t_sub0 = time.perf_counter()
        try:
            client.game_action(gid, act)
        except ApiError as e:
            sub_ms = round((time.perf_counter() - t_sub0) * 1000.0, 1)
            if e.status == 409:
                # 动作已失效（竞态 / 窗口已响应 / 自判失误）：全量重建状态；
                # 窗口期 409 = 本窗口已死（服务器已代处理），标记不再重试
                log("动作 409（已失效）: %s phase=%s act=%s sub_ms=%s",
                    e.code or e.body[:120], phase,
                    (act or {}).get("action"), sub_ms)
                sub = "409"
                if phase.startswith("response_"):
                    last_window_key = window_key
                    # R1096：响应窗口 409 = 本窗口已死（服务端已代处理），**我方动作被拒**
                    # ⇒ 游戏状态未被我方改变，不需要整体重同步。保留水位可继续消费事件；
                    # 反例：旧实现无条件 `seq = 0`，会把两次请求之间的事件整段丢掉，
                    # 其中包括 round_ended（river 不重置）⇒ 今日实测本地河比权威"多 6.31 张"。
                else:
                    seq = 0

            elif e.status in (0, 429) or e.status >= 500:
                # 网络瞬断 / 限速 / 服务端暂错：稍候重试（水位不变，继续挂起）
                log("瞬时故障(%s)，1s 后继续" % (e.code or e.status))
                sub = "err"
                time.sleep(1.0)
            else:
                raise
        else:
            sub = "ok"
            sub_ms = round((time.perf_counter() - t_sub0) * 1000.0, 1)
            tracker.record_action(act)      # 提交成功 → 副露本地累计
            if act.get("action") in ("discard", "hu"):
                self_drawn = ""             # 已打出/胡掉的刚摸牌，防残留
            # R1101c：我方弃牌成功后同步缓存手牌——窗口发生在"我方弃牌之后"，
            # 若不更新，缓存必然多一张（=刚弃的那张），缓存窗口决策就永远对不上。
            if act.get("action") == "discard" and last_hand:
                _lh = list(last_hand)
                try:
                    _lh.remove(act.get("tile"))
                    last_hand = _lh
                except ValueError:
                    pass
                last_drawn = ""
                self_replenish = False      # 杠补牌已被处置，杠形态标记清空
            if act.get("action") == "gang" and phase == "draw":
                # 本人在摸牌回合自杠（暗杠/补杠）成功：此后整个 round 服务器
                # my_hand 恒多计该杠组第 4 张，记入本局自杠集合，供后续每回合
                # 按集合逐个抽掉。同局不同牌面各自 +1，集合逐个移除防标量覆盖。
                t = act.get("tile") or None
                if t and t not in self_gang_tiles:
                    self_gang_tiles.append(t)
        if phase.startswith("response_"):
            last_window_key = window_key    # 本窗口已响应（无论成败）
        else:
            decided_seq_sig = sig
        if dr is not None and sub is not None:
            dr["sub"] = sub
            dr["sm"] = sub_ms
            recorder.on_decision(gid, dr)   # 提交结果并入该决策记录（见上 noop 分支）
        # 注意：动作成功后【不】回退 seq=0 —— 保持当前水位挂起长轮询，
        # 否则每次全量快照会跳过 tile_drawn 等增量事件（真机摸牌信息只经事件流）
        continue
