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
from .model import snap_view
from .util import log


def _end_reason(res, snap):
    """场次是否结束及原因：响应的 finished 标记 / 快照 phase==finished。"""
    if res.get("finished"):
        return "finished 标记"
    if snap is not None and snap.get("phase") == "finished":
        return "phase=finished"
    return None


def play_game(client, gid, strategy):
    """打一场：返回该场结束时快照（含 scores），或 None（异常中止由调用方决定）。"""
    seq = 0
    pending_count = 0           # 连续长挂起计数（防漏窗口兜底）
    last_window_key = None      # 最近已响应的窗口键 (phase, turn)
    decided_seq_sig = None      # 非窗口最近已决策的 (phase, seq) —— 防 409 死循环
    self_drawn = ""             # 最近一次本人摸牌（tile_drawn 事件，tile 仅自己可见）
    self_offer = None           # 最近弃牌 (tile, seat)（tile_discarded 事件，公开）
    river = []                  # 当前局公开弃牌河（round_ended 清空）
    tracker = MeldTracker()     # 本人副露跟踪（真机快照无 melds，本地累计）
    while True:
        res = client.game_state(gid, seq)
        snap = res.get("snapshot")

        reason = _end_reason(res, snap)
        if reason:
            log("本场结束: %s（gid=%s）", reason, gid)
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
                seq = max(seq, int(ev.get("seq", seq)))
                etype = ev.get("type")
                if etype == "round_ended":
                    river = []          # 新局开始：弃牌河清空
                    tracker.reset()     # 新局：副露清零（跨局残留曾致整局误判）
                    self_drawn = ""
                    self_offer = None
                elif etype == "tile_drawn" and ev.get("tile"):
                    self_drawn = ev["tile"]     # 非空 tile = 本人刚摸
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
            # 服务器快照语义：多数为不含刚摸（expect-1），但实测副露后部分
            # 路径快照已含刚摸（=expect）——按张数判断，避免重复注入
            if len(hand) == expect_hold - 1 and drawn_tile not in hand:
                hand.append(drawn_tile)      # 不含 → 补第 N 张
                view["my_hand"] = hand
                view["drawn_tile"] = drawn_tile
            elif len(hand) != expect_hold:
                # claim 后服务器瞬时仍回「扣减前」旧手牌（len 偏大、
                # 与已 +1 的副露数冲突）→ 本轮放弃出牌，等事件推进同步；
                # 若正处于窗口期，先标记已响应防重复提交（409 风暴源）
                log("手牌形态暂不一致 len=%d expect=%d e=%d g=%d —— 跳过本轮",
                    len(hand), expect_hold, exposed, gangs)
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
        try:
            act = strategy.decide(view)
        except Exception as e:
            # 策略异常（真机边缘局面）→ 窗口 pass / 非窗口不动作（等超时兜底）
            log("策略异常(%s: %s)——按 pass/等待处理" % (type(e).__name__,
                                                    str(e)[:100]))
            if phase.startswith("response_"):
                act = {"action": "pass", "tile": ""}
            else:
                last_window_key = window_key if phase.startswith(
                    "response_") else last_window_key
                continue
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
        try:
            client.game_action(gid, act)
        except ApiError as e:
            if e.status == 409:
                # 动作已失效（竞态 / 窗口已响应 / 自判失误）：全量重建状态
                log("动作 409（已失效）:", e.code or e.body[:120])
                seq = 0
            elif e.status in (0, 429) or e.status >= 500:
                # 网络瞬断 / 限速 / 服务端暂错：稍候重试（水位不变，继续挂起）
                log("瞬时故障(%s)，1s 后继续" % (e.code or e.status))
                time.sleep(1.0)
            else:
                raise
        else:
            tracker.record_action(act)      # 提交成功 → 副露本地累计
            if act.get("action") == "discard":
                self_drawn = ""             # 已打出刚摸牌，防残留
        if phase.startswith("response_"):
            last_window_key = window_key    # 本窗口已响应（无论成败）
        else:
            decided_seq_sig = sig
        # 注意：动作成功后【不】回退 seq=0 —— 保持当前水位挂起长轮询，
        # 否则每次全量快照会跳过 tile_drawn 等增量事件（真机摸牌信息只经事件流）
        continue
