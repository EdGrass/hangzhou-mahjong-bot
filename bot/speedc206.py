# -*- coding: utf-8 -*-
"""SpeedC206 —— **爆头导向**的 V1（只在 s=1 时）：把"白 → 任意牌听"的转化率当成目标。

依据 R550：我们与 top32 的**胡牌时白数分布几乎相同**，但在每个白数档上他们的爆头率都高 6~12pp
⇒ 价值缺口是**可转化的技术差异**（+4.6pp 爆头占胡 ≈ +15 分/房）。

定义（与 c205 同构，只换叶子值）：
    B1(rem) = Σ_{t ∈ rem 的进张} live(t) × max_{d'} is_baotou(rem + t − d')
其中 is_baotou = "摸任意一张都能胡"（mahjong.hu.is_baotou）。s≠1 时完全退回 c135。
"""
from __future__ import annotations
import time
from mahjong.hu import is_baotou
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedc135 import _best_discard_realukeire
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts

TILES = [t + s for s in ("w", "b", "t") for t in "123456789"] + ["东", "南", "西", "北", "中", "发", "白"]


class SpeedC206(SpeedTUGC):
    CAP = 8
    BUDGET_MS = 150.0

    def __init__(self, name="speedc206"):
        super().__init__(name)

    def _b1(self, rem, vis, e, g, s_now, deadline, want_bai):
        total = 0.0; n = 0
        for t in TILES:
            if time.monotonic() >= deadline: break
            live = 4 - int((vis or {}).get(t, 0))
            if live <= 0: continue
            ok = False
            for d in set(rem):
                hh = list(rem); hh.remove(d); hh.append(t)
                try:
                    if exact_shanten(hh, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g) < s_now:
                        ok = True; break
                except Exception: continue
            if not ok: continue
            h14 = list(rem); h14.append(t)
            hit = 0.0
            for d in sorted(set(h14)):
                hh = list(h14); hh.remove(d)
                try:
                    if is_baotou(hh, allow_qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g):
                        hit = 1.0; break
                except Exception: continue
            total += live * hit
            n += 1
            if n >= self.CAP: break
        return total

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
        # 只在"手上有白"且 s=1 时启用（否则没有爆头可谈，直接退回 c135）
        if smin != 1 or "白" not in hand:
            return _best_discard_realukeire(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view)
        deadline = time.monotonic() + self.BUDGET_MS / 1000.0
        scored = []
        for d, rem, s in cands:
            if s != 1: continue
            try: u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
            except Exception: u1 = 0.0
            b1 = self._b1(rem, vis, exposed, gangs, 1, deadline, True)
            scored.append((d, b1, u1))
        if not scored or time.monotonic() >= deadline:
            return _best_discard_realukeire(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view)
        best = min(scored, key=lambda x: (-x[1], -x[2], _pref(x[0], hand), -1 if x[0] == drawn else 0))
        return best[0]
