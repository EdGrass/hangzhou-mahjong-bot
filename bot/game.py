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
    decided_sig = None          # 最近一次已决策的 (phase, seq) —— 窗口去重
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
        if view["seat"] < 0:
            continue            # 观赛视角无动作权

        # 窗口去重：同一 (phase, seq) 局面已决策过（含提交失败=已响应），不再重复提交
        sig = (view["phase"], seq)
        act = strategy.decide(view)
        if act is None or sig == decided_sig:
            continue

        log("提交:", act, "phase=%s turn=%s" % (view["phase"], view["turn"]))
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
        decided_sig = sig       # 本局面已决策（无论成败）
        seq = 0                 # 动作后重建权威快照，避免状态漂移
