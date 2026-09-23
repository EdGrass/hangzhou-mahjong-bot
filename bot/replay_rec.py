"""replay_rec —— 逐场记录器（run_bot --record-replays <目录> 时启用）。

两类记录，同一目录、同 gid 双文件：
- <gid>.jsonl      事件流（long-poll 增量事件，同 seq 去重后落盘）；
- <gid>.dec.jsonl  决策记录（每条 = 策略一次真实决策的完整信息局面 + 动作 +
                    耗时 + 提交结果，见 bot/game.py on_decision 调用点）。

决策记录是「执行验证」的数据底座（P2/P3 基建）：
- 事后可证明某候选"是否真的差异化执行"（分歧局面/触发率统计），
- 可离线用任意策略对同一局面重决策（oracle 评估），
- 含 decide/submit 耗时 → 判断 1s/3s 窗口超时假说。
字段约定（紧凑键，见 game.py _dr_payload）：k/g/s/p/t/q/h/d/o/m/god/r/a/ms/sub。
"""
from __future__ import annotations

import json
import os


class ReplayRecorder:
    def __init__(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir = out_dir
        self._buf = {}
        self._dec = {}

    # ---------- 事件流 ----------
    def on_event(self, gid, event):
        if not gid or not isinstance(event, dict):
            return
        self._buf.setdefault(gid, []).append(event)

    # ---------- 决策记录 ----------
    def on_decision(self, gid, rec):
        """记录一条决策（rec: dict，键见模块 docstring）。gid 为空则忽略。"""
        if not gid or not isinstance(rec, dict):
            return
        self._dec.setdefault(gid, []).append(rec)

    def _flush_lines(self, gid, lines, suffix):
        if not lines:
            return
        safe = "".join(c for c in str(gid) if c.isalnum() or c in "_-")[:80]
        with open(os.path.join(self.out_dir, safe + suffix), "a",
                  encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def close_game(self, gid):
        """场次结束：事件与决策分别落盘（幂等）。"""
        evs = self._buf.pop(gid, [])
        if evs:
            evs.sort(key=lambda e: int(e.get("seq", 0)))
            keep = []
            for e in evs:
                if keep and keep[-1].get("seq") == e.get("seq"):
                    keep[-1] = e            # 同 seq 只保留最后一条
                else:
                    keep.append(e)
            self._flush_lines(gid, keep, ".jsonl")
        decs = self._dec.pop(gid, [])
        if decs:
            self._flush_lines(gid, decs, ".dec.jsonl")
