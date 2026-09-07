"""replay_rec —— 逐场事件记录器（run_bot --record-replays <目录> 时启用）。

game.py 的 long-poll 每收到一批事件即回调 on_event；场次结束（finished 标记
或 round 终态）调 close_game 落盘 <gid>.jsonl（事件按 seq 排序）。
用途：窗口赛后审计的数据源（对手摸牌不可见——如需全桌含手牌，仍走
tools/replay_fetch.py 拉服务器复盘，本记录器为保底）。
"""
from __future__ import annotations

import json
import os


class ReplayRecorder:
    def __init__(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir = out_dir
        self._buf = {}

    def on_event(self, gid, event):
        if not gid or not isinstance(event, dict):
            return
        self._buf.setdefault(gid, []).append(event)

    def close_game(self, gid):
        evs = self._buf.pop(gid, [])   # 幂等：已 close 过则 pop 为空直接返回
        if not evs:
            return
        # 同 seq 只保留最后一条（异常/重播复用缓冲不致事件重复后再排序落盘）
        evs.sort(key=lambda e: int(e.get("seq", 0)))
        keep = []
        for e in evs:
            if keep and keep[-1].get("seq") == e.get("seq"):
                keep[-1] = e            # 覆盖旧的那条
            else:
                keep.append(e)
        evs = keep
        safe = "".join(c for c in str(gid) if c.isalnum() or c in "_-")[:80]
        with open(os.path.join(self.out_dir, safe + ".jsonl"), "a",
                  encoding="utf-8") as f:
            for e in evs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
