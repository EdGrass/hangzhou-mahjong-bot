# -*- coding: utf-8 -*-
"""SpeedC207 —— **c135（速度） + 爆头可达性值函数 V（价值）** 的加权候选。

依据：
  - R550：我们与 top32 的唯一可控差距 = "同样白数下把白变成爆头的转化率"（+6~12pp/档 ≈ +16 分/房）；
  - R559：值函数 V(post-discard 状态) → P(该局以爆头胡)，**局级 AUC 0.771**、分位极差 12 倍；
  - R545/R546：**并列项改不动**（分歧 1~5%）⇒ 本候选把 V 作为**加权主项**（`u1 + W·V`），
    并允许用 W 把分歧率调到 ≥10%（可判的强度）。

键：`(s, -wcnt, -(u1 + W·V), _pref, 保留摸切)`；W 由环境变量 C207_W 控制。
"""
from __future__ import annotations
import os, time
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts
from .baotou_value import value as _V

class SpeedC207(SpeedTUGC):
    W = float(os.environ.get("C207_W", "20"))
    BUDGET_MS = 400.0

    def __init__(self, name="speedc207"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        vis = None
        if view:
            try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            except Exception: vis = None
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try: s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0), exposed_melds=exposed, gangs=gangs)
            except Exception: continue
            cands.append((d, rem, s))
        if not cands: return hand[0]
        smin = min(c[2] for c in cands)
        deadline = time.monotonic() + self.BUDGET_MS / 1000.0
        best_key, best_tile = None, None
        god = (view or {}).get("god") or {}
        river = (view or {}).get("river") or []
        all_melds = (view or {}).get("all_melds") or []
        draw_idx = int((view or {}).get("draw_idx") or 0)
        for d, rem, s in cands:
            if s != smin: continue
            if s == 0:
                try: wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
                except Exception: wcnt = 0
                u1 = 0.0
            else:
                wcnt = 0
                try: u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
                except Exception: u1 = 0.0
            v = 0.0
            if time.monotonic() < deadline:
                try: v = _V(rem, exposed, gangs, river, all_melds, god, draw_idx, vis=vis)
                except Exception: v = 0.0
            key = (s, -wcnt, -(u1 + self.W * v), _pref(d, hand), -1 if d == drawn else 0)
            if best_key is None or key < best_key: best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
