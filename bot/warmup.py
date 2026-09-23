# -*- coding: utf-8 -*-
"""进程内预热：用真实历史出牌局面填充策略的内部缓存。

为什么：c151 的 M=10 冷启动实测 4/160 次 >3s；相同进程先预热 50 个真实 draw
局面后，同一压测变为 0/160。官方 keepalive 会在开赛前给重型策略传
`--warmup-draws 50`，让 20:00 的比赛以热缓存开始。

安全边界：只读 `var/replays/auto_*/*.dec.jsonl`，只调用 `policy.decide(view)`，
不提交动作、不写状态；任何异常都不阻断主流程。
"""
from __future__ import annotations

import glob
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _to_view(rec):
    melds = []
    for m in rec.get("m") or []:
        if isinstance(m, dict):
            melds.append(dict(m))
        elif isinstance(m, (list, tuple)) and len(m) >= 2:
            melds.append({"type": m[0], "tile": m[1], "tiles": [m[1]]})
    phase = rec.get("p")
    god = rec.get("god") or {}
    return {
        "seat": rec.get("s"), "phase": phase, "turn": rec.get("t"),
        "responding_seats": [rec.get("s")] if str(phase).startswith("response_") else [],
        "my_hand": list(rec.get("h") or []), "melds": melds,
        "drawn_tile": rec.get("d"), "offer_tile": rec.get("o"),
        "river": list(rec.get("r") or []), "river_len": len(rec.get("r") or []),
        "all_melds": [],
        "god": {"baotou": bool(god.get("b")), "chain_count": int(god.get("cc") or 0),
                "catch_play": bool(god.get("cp")), "piao_count": int(god.get("p") or 0),
                "god_discarder_seat": int(god.get("gd", -1) or -1)},
    }


def warmup_strategy(policy, n=0, replay_root=None):
    """最多用 n 个真实 draw 局面预热 policy；返回成功调用 decide 的次数。"""
    try:
        n = int(n)
    except Exception:
        return 0
    if n <= 0:
        return 0
    root = str(replay_root or os.path.join(ROOT, "var", "replays"))
    paths = glob.glob(os.path.join(root, "auto_*", "*.dec.jsonl"))
    try:
        paths.sort(key=os.path.getmtime, reverse=True)
    except Exception:
        paths.sort()
    done = 0
    for path in paths:
        try:
            fh = io.open(path, encoding="utf-8")
        except OSError:
            continue
        try:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                if rec.get("p") != "draw" or not rec.get("d"):
                    continue
                if len(rec.get("h") or []) < 13:
                    continue
                try:
                    policy.decide(_to_view(rec))
                    done += 1
                except Exception:
                    continue
                if done >= n:
                    return done
        finally:
            try:
                fh.close()
            except Exception:
                pass
    return done
