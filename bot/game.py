"""单局（场次）主循环：seq 长轮询 / 快照权威 / 动作提交与竞态恢复。

协议要点（指南 §2.1）：
- seq=S 的响应已含全部 ≤S 事件，快照是规范真相；
- 快照无 allowed_actions —— 动作合法性由策略层自行判断，服务端纯验证；
- 丢帧（gap）/ 动作 409 后，用 seq=0 重建全量快照；
- 窗口「已响应」须客户端本地跟踪，重复提交 pass/动作返回 409 INVALID_ACTION。
"""
from __future__ import annotations

import os
import time

from .api import ApiError
from .meldtrack import MeldTracker
from .model import my_turn, snap_view, window_pending
from .util import log


def _dr_payload(gid, view, seq, river, ms, act):
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
            "r": list(river or []), "a": act, "ms": round(float(ms or 0), 1)}


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
    场次结束回调 close_game(gid) 落盘该场事件流。"""
    seq = 0
    pending_count = 0           # 连续长挂起计数（防漏窗口兜底）
    last_window_key = None      # 最近已响应的窗口键 (phase, turn)
    decided_seq_sig = None      # 非窗口最近已决策的 (phase, seq) —— 防 409 死循环
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
    tracker = MeldTracker()     # 本人副露跟踪（真机快照无 melds，本地累计）
    while True:
        res = client.game_state(gid, seq)
        snap = res.get("snapshot")

        reason = _end_reason(res, snap)
        if reason:
            log("本场结束: %s（gid=%s）", reason, gid)
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
            for ev in res.get("events") or []:
                if recorder:
                    recorder.on_event(gid, ev)
                seq = max(seq, int(ev.get("seq", seq)))
                etype = ev.get("type")
                if etype == "round_ended":
                    river = []          # 新局开始：弃牌河清空
                    tracker.reset()     # 新局：副露清零（跨局残留曾致整局误判）
                    self_drawn = ""
                    self_replenish = False
                    self_gang_tiles = []    # 新局：自杠 round 级幻影集合清空
                    self_offer = None
                elif etype == "tile_drawn" and ev.get("tile"):
                    self_drawn = ev["tile"]     # 非空 tile = 本人刚摸
                    # 杠补牌：服务器把该牌并入快照 my_hand（标记后续按"去补"处理）
                    self_replenish = bool((ev.get("data") or {}).get(
                        "gang_replenish"))
                elif etype == "tile_discarded" and ev.get("tile"):
                    self_offer = (ev["tile"], ev.get("seat"))   # 弃牌牌面（公开）
                    river.append(ev["tile"])
            auth = client.game_state(gid, 0)
            snap = auth.get("snapshot")
            if snap is None:
                continue
            seq = max(seq, int(auth.get("seq", seq)))
        else:
            seq = int(res.get("seq", seq))

        view = snap_view(snap)
        view.update(tracker.view_extra())   # 注入本人副露（策略 view 扩展键）
        view["river"] = list(river)         # 注入公开弃牌河（SpeedG 已见扣减用）
        if view["seat"] < 0:
            continue            # 观赛视角无动作权

        # 窗口 offer 注入：快照无 offer_tile（敏感牌面仅事件流公开）——
        # 窗口期（response_*）若事件流给出弃牌牌面，则补入 view
        if self_offer is not None:
            offer_tile, offer_seat = self_offer
            if view["phase"].startswith("response_") and \
                    view.get("turn") == offer_seat:
                view["offer_tile"] = offer_tile
        # 本人出牌后清掉过期 offer（同弃牌不重复评估）
        if self_offer is not None and view["phase"] == "draw" and \
                view.get("turn") == view["seat"]:
            self_offer = None

        # 真机手牌语义：权威快照 my_hand 恒为「不含刚摸牌」的 13-3e-g 张，
        # 本人摸牌只经 tile_drawn 事件（tile 仅对自己可见）传达 → 把最近一次
        # 本人摸牌并入 view，策略才能判胡/算向听（引擎视角 = 摸后 14 张）。
        drawn_tile = view.get("drawn_tile") or ""
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
            if len(hand) == expect_hold:
                # 长度已对齐 expect（可能经自杠逐张抽除，或原本就含刚摸）：与已
                # 计入 e/g 的杠组一致，交策略正常决策（仍留 drawn_tile 供判杠上/弃牌）。
                view["my_hand"] = hand
                if self_gang_tiles:
                    log("自杠当局核对完成: len=%d expect=%d —— 继续决策",
                        len(hand), expect_hold)
            elif len(hand) == expect_hold - 1 and drawn_tile not in hand:
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
                log("  [debug] snap_hand=%s drawn=%r self_gang_tiles=%s self_replenish=%r",
                    ",".join(sorted(hand)), drawn_tile, self_gang_tiles,
                    locals().get("self_replenish", None))
                if view["phase"].startswith("response_"):
                    last_window_key = (view["phase"], view["turn"])
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
        t_dec0 = time.perf_counter()
        dr_exc = False
        try:
            act = strategy.decide(view)
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
            dr = _dr_payload(gid, view, seq, river, dec_ms, act)
        elif recorder:
            if my_turn(view) or window_pending(view) or dec_ms > 100 or dr_exc:
                drp = _dr_payload(gid, view, seq, river, dec_ms, None)
                drp["sub"] = "noop"
                recorder.on_decision(gid, drp)
        # 通用分歧探针（HM_XLOG=1 且非基准策略）：同局面基准重决策，
        # 动作不同即记 [xlog]——执行验证：候选差异是否真实发生（离线可数）。
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
        if act is None:
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
