"""单局（场次）主循环：seq 长轮询 / 快照权威 / 动作提交与竞态恢复。

协议要点（指南 §2.1）：
- seq=S 的响应已含全部 ≤S 事件，快照是规范真相；
- 快照无 allowed_actions —— 动作合法性由策略层自行判断，服务端纯验证；
- 丢帧（gap）/ 动作 409 后，用 seq=0 重建全量快照；
- 窗口「已响应」须客户端本地跟踪，重复提交 pass/动作返回 409 INVALID_ACTION。
"""
from __future__ import annotations

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
    last_window_key = None      # 最近已响应的窗口键 (phase, turn)
    decided_seq_sig = None      # 非窗口最近已决策的 (phase, seq) —— 防 409 死循环
    tracker = MeldTracker()     # 本人副露跟踪（真机快照无 melds，本地累计）
    while True:
        res = client.game_state(gid, seq)
        snap = res.get("snapshot")

        reason = _end_reason(res, snap)
        if reason:
            log("本场结束: %s（gid=%s）", reason, gid)
            if snap and snap.get("scores") is not None:
                log("本场积分:", snap["scores"])
            return snap

        if res.get("pending"):
            continue            # 30s 内无新事件：继续挂起

        if snap is None:
            # 增量事件：推进 seq 后重建权威快照再决策
            for ev in res.get("events") or []:
                seq = max(seq, int(ev.get("seq", seq)))
            auth = client.game_state(gid, 0)
            snap = auth.get("snapshot")
            if snap is None:
                continue
            seq = max(seq, int(auth.get("seq", seq)))
        else:
            seq = int(res.get("seq", seq))

        view = snap_view(snap)
        view.update(tracker.view_extra())   # 注入本人副露（策略 view 扩展键）
        if view["seat"] < 0:
            continue            # 观赛视角无动作权

        # 窗口去重（真机语义）：同一窗口（phase+弃牌者 turn）只响应一次；
        # 窗口内其他玩家的响应会推进 seq 但窗口未关——重复 pass/claim 会 409，
        # 故以 (phase, turn) 为窗口键幂等跳过（新窗口 = 新 turn 或新 phase）。
        phase = view["phase"]
        window_key = (phase, view["turn"])
        if phase.startswith("response_"):
            if window_key == last_window_key:
                continue
        # 非窗口（draw/deal 等）：同 (phase, seq) 局面不重复决策，防 409 死循环
        sig = (phase, seq)
        if not phase.startswith("response_") and sig == decided_seq_sig:
            continue
        act = strategy.decide(view)
        if act is None:
            continue

        log("提交:", act, "phase=%s turn=%s" % (phase, view["turn"]))
        try:
            client.game_action(gid, act)
        except ApiError as e:
            if e.status == 409:
                # 动作已失效（竞态 / 窗口已响应 / 自判失误）：记录后重建快照
                log("动作 409（已失效）:", e.code or e.body[:120])
            elif e.status == 0 or e.status >= 500:
                # 网络瞬断 / 服务端暂错：稍候重试
                log("瞬时故障(%s)，1s 后继续" % (e.code or e.status))
                time.sleep(1.0)
            else:
                raise
        else:
            tracker.record_action(act)      # 提交成功 → 副露本地累计
        if phase.startswith("response_"):
            last_window_key = window_key    # 本窗口已响应（无论成败）
        else:
            decided_seq_sig = sig
        seq = 0                 # 动作后重建权威快照，避免状态漂移
