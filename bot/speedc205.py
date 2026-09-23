# -*- coding: utf-8 -*-
"""SpeedC205 —— **只在"一向听（s=1）"时改用和了导向的目标**：max V1 而不是 max u1。

动机（R543）：c135 把听牌率提上去，却把"听牌后的活等张"压了 0.71 张 ⇒ 和了率只 +0.84pp。
在 s=1 的那个弃牌，**正是决定最终待ち形状的一手**。
定义（一层值函数，叶子=活的和了张数）：
    V0(h13)  = 若已听牌，活的和了张数；否则 0
    V1(rem)  = Σ_{t ∈ rem 的进张} live(t) × max_{d'} V0(rem + t − d')
  ⇒ 它近似的就是"再摸一张之后，手上能和的张数"（= 两摸内的和了期望），天然含"待ち宽度"。
代价实测：只对 s=1 候选、每候选最多 8 个进张 ⇒ p50≈0ms / max≈67ms ⇒ 可用（带硬时限兜底）。
s≠1 时**完全退回 c135**（不改任何决策）。
"""
from __future__ import annotations
import time
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedc135 import _best_discard_realukeire
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts

TILES = [t + s for s in ("w", "b", "t") for t in "123456789"] + ["东", "南", "西", "北", "中", "发", "白"]


class SpeedC205(SpeedTUGC):
    CAP = 8
    BUDGET_MS = 120.0

    def __init__(self, name="speedc205"):
        super().__init__(name)

    @staticmethod
    def _v0(h13, vis, e, g):
        try:
            if exact_shanten(h13, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g) != 0:
                return 0.0
            w = waits(h13, exposed_melds=e, gangs=g)
        except Exception:
            return 0.0
        return float(sum(max(0, 4 - int((vis or {}).get(t, 0))) for t in w))

    def _v1(self, rem, vis, e, g, s_now, deadline):
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
            best = 0.0
            for d in set(h14):
                hh = list(h14); hh.remove(d)
                v = self._v0(hh, vis, e, g)
                if v > best: best = v
            total += live * best
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
        if not cands:
            return hand[0]
        smin = min(c[2] for c in cands)
        if smin != 1:
            return _best_discard_realukeire(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view)
        deadline = time.monotonic() + self.BUDGET_MS / 1000.0
        scored = []
        for d, rem, s in cands:
            if s != 1: continue
            try: u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
            except Exception: u1 = 0.0
            v1 = self._v1(rem, vis, exposed, gangs, 1, deadline)
            scored.append((d, v1, u1))
        if not scored or time.monotonic() >= deadline:
            return _best_discard_realukeire(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view)
        best = min(scored, key=lambda x: (-x[1], -x[2], _pref(x[0], hand), -1 if x[0] == drawn else 0))
        return best[0]
