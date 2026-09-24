# -*- coding: utf-8 -*-
"""C118 学生策略：C073-w4 + 自杠（暗杠/补杠）。

动机（2026-09-15 完整复盘 + 我方决策日志）：
  - 真机全场 杠事件 0.149/局桌（明杠 0.077 / 补杠 0.051 / 暗杠 0.022）；
    我方 0.01/局桌（几乎全是明杠），**暗杠/补杠 0 次**（1020 个可杠窗口全部放弃）；
  - 杠 = 多摸一张 + 杠开 ×2 番；白板禁杠、抓打圈内非本人禁补杠、牌墙余量限制。
本策略只在「自杠窗口」给出 gang 动作，其余完全沿用 C068/C073 家族。
"""
from __future__ import annotations

import os

from .model import my_turn, window_pending
from .speedc068 import C068Policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c073_orig_w4_net.pt")

GOD = "白"
RIVER_GUARD = 50          # 保守：整局弃牌数超过此值不再自杠（真机牌墙余量限制）


class C118Policy(C068Policy):
    def __init__(self, name="speedc118", model_path=None, lo=0, hi=2, **kw):
        super().__init__(name=name, model_path=model_path or DEFAULT_MODEL,
                         lo=lo, hi=hi, **kw)

    def _try_kong(self, view):
        if not my_turn(view) or (window_pending(view) and view.get("offer_tile")):
            return None
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        if drawn is None or len(hand) != 14 - 3 * exposed - gangs:
            return None
        river = view.get("river") or []
        if len(river) > RIVER_GUARD:
            return None
        catch = bool((view.get("god") or {}).get("catch_play"))
        # 补杠：碰组 + 手里第 4 张（抓打圈内非本人禁补杠）
        if not catch:
            for m in melds:
                if not isinstance(m, dict):
                    continue
                t = m.get("tile")
                if m.get("type") == "peng" and t and t != GOD and hand.count(t) >= 1:
                    return {"action": "gang", "tile": t}
        # 暗杠：自摸 4 张同码（白板禁杠）
        for t in sorted(set(hand)):
            if t == GOD:
                continue
            if hand.count(t) == 4:
                return {"action": "gang", "tile": t}
        return None

    def decide(self, view):
        try:
            act = self._try_kong(view)
        except Exception:
            act = None
        if act is not None:
            self.stats["kong"] += 1
            return act
        return super().decide(view)
