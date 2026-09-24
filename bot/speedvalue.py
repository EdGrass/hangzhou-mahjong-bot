# -*- coding: utf-8 -*-
"""Value-weighted discard policy (M3): replace "max live ukeire" with the fitted V.

Why not the raw regression: with the full feature set the sh=1 `ukeire`
coefficient swings between +0.096 and +1.14 (collinearity with pairs/honors/
terminals), so the fitted weights are not stable enough to drive a 100%-coverage
policy.  The MINIMAL feature set is stable across two independent samples:

    feature                 7 rooms     143 rooms   (points per round)
    1 live ukeire tile @sh1   +0.080      +0.096
    1 live wait tile @sh0     +0.118      +0.211
    1 fan @sh0 (max over waits) +3.75      +2.42
    holding 白                +3.70      +4.57

This arm scores every min-shanten discard with that small, stable V and picks the
argmax, i.e. it is the first candidate whose footprint is a large share of the
discard decisions (earlier arms covered 0.3-7.5%).  Everything else (meld gate,
gang handling, route chain) is inherited from `SpeedC151` unchanged, and any
exception falls back to it.

Weights are conservative: the smaller of the two fitted values for each feature.
"""
from __future__ import annotations

import collections

from mahjong.fan import calc as fan_calc
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc151 import SpeedC151
from .ukeire import real_ukeire, visible_counts


class SpeedValue(SpeedC151):
    #: points per live ukeire tile, by shanten (the within-bucket slope)
    W_UKEIRE = {0: 0.0, 1: 0.080, 2: 0.0021, 3: 0.0261, 4: 0.02, 5: 0.02}
    W_LIVE_WAIT = 0.118      # tenpai only: points per live wait tile
    W_MAX_FAN = 2.42         # tenpai only: points per extra fan
    W_BAI = 3.70             # points per 白 held
    MARGIN = 0.0             # set >0 to require a strictly better V by this margin

    def __init__(self, name="speedvalue"):
        super().__init__(name)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _counts(hand):
        cnt = collections.Counter(hand)
        pairs = sum(1 for v in cnt.values() if v >= 2)
        return pairs, cnt.get("白", 0)

    @staticmethod
    def _max_fan(rem, e, g, view):
        try:
            ws = waits(rem, exposed_melds=e, gangs=g)
        except Exception:
            return 0.0
        if not ws:
            return 0.0
        god = (view or {}).get("god") or {}
        chain = {"count": int(god.get("chain_count") or 0),
                 "piao": int(god.get("piao_count") or 0)}
        best = 0.0
        for wt in ws:
            try:
                r = fan_calc(list(rem), wt, chain, base=1, exposed_melds=e, gangs=g)
            except Exception:
                continue
            if r.get("hu"):
                f = float(r.get("fan") or 0)
                if f > best:
                    best = f
        return best

    def value_of(self, rem, e, g, vis, view, sh):
        """V(state) in round points, from the minimal fitted model."""
        try:
            u = real_ukeire(rem, exposed=e, gangs=g, visible=vis)[0]
        except Exception:
            return None
        if u is None:
            return None
        v = float(u) * self.W_UKEIRE.get(sh, 0.02)
        if sh == 0:
            try:
                ws = waits(rem, exposed_melds=e, gangs=g)
            except Exception:
                ws = []
            live = sum(max(0, 4 - int(vis.get(t, 0))) for t in ws)
            v += live * self.W_LIVE_WAIT
            v += self._max_fan(rem, e, g, view) * self.W_MAX_FAN
        _, bai = self._counts(rem)
        v += bai * self.W_BAI
        return v

    # -- policy --------------------------------------------------------------
    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = SpeedC151._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        if not view or base not in hand:
            return base
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            return base
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            if len(rem) != 13 - 3 * exposed - gangs:
                continue
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs,
                                  god_meld=self.GOD_MELD)
            except Exception:
                continue
            cands.append((d, rem, s))
        if not cands:
            return base
        smin = min(c[2] for c in cands)
        scored = []
        base_v = None
        for d, rem, s in cands:
            if s != smin:
                continue
            v = self.value_of(rem, exposed, gangs, vis, view, s)
            if v is None:
                continue
            scored.append((d, v))
            if d == base:
                base_v = v
        if not scored or base_v is None:
            return base
        best_d, best_v = max(scored, key=lambda x: (x[1], -1 if x[0] != base else 0))
        if best_d == base or best_v - base_v <= self.MARGIN:
            return base
        return best_d


# ---------------------------------------------------------------------------
# Per-term ablations (each switches off exactly one value term).
# Purpose: find out WHICH fitted term carries the arena gain, so the promoted
# candidate can be as small and as safe as possible.
# ---------------------------------------------------------------------------
class SpeedValueNoBai(SpeedValue):
    """Drop the 白 (god tile) term -- the largest single coefficient."""

    W_BAI = 0.0

    def __init__(self, name="speedvaluenobai"):
        super().__init__(name)


class SpeedValueNoFan(SpeedValue):
    """Drop the tenpai fan term."""

    W_MAX_FAN = 0.0

    def __init__(self, name="speedvaluenofan"):
        super().__init__(name)


class SpeedValueNoLive(SpeedValue):
    """Drop the tenpai live-wait term."""

    W_LIVE_WAIT = 0.0

    def __init__(self, name="speedvaluenolive"):
        super().__init__(name)


class SpeedValueFlatUkeire(SpeedValue):
    """Use one ukeire weight for every shanten (no per-bucket slope)."""

    W_UKEIRE = {0: 0.0, 1: 0.08, 2: 0.08, 3: 0.08, 4: 0.08, 5: 0.08}

    def __init__(self, name="speedvalueflatukeire"):
        super().__init__(name)


class SpeedValueToggle(SpeedValue):
    """Ablation switchboard: set ATTRS = {'W_BAI': 0.0, ...} to disable terms."""

    ATTRS = {}

    def __init__(self, name="speedvaluetoggle"):
        super().__init__(name)
        for k, v in self.ATTRS.items():
            setattr(self, k, v)


class SpeedTenpaiValue(SpeedValue):
    """The gain, restricted to the tenpai decision -- everything else is c151.

    Evidence (R988/R992): the 7.1% footprint of `SpeedValue` vs c151 is exactly
    "no pair penalty", and removing the pair penalty ALONE is neutral on the
    arena win endpoint (route0: t=+0.03, n=100).  The term that actually moves
    the needle sits at tenpai (~2.6% of decisions: live wait tiles + fan).

    So this arm keeps c151's chooser everywhere except when c151's own choice
    lands on tenpai; there it re-orders by the fitted value (live waits, fan,
    then 白).  Smaller footprint => smaller downside if the arena result does not
    transfer to the real server.
    """

    def __init__(self, name="speedtenpaivalue"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = SpeedC151._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        if not view or base not in hand:
            return base
        rem0 = list(hand)
        rem0.remove(base)
        try:
            s0 = exact_shanten(rem0, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs,
                               god_meld=self.GOD_MELD)
        except Exception:
            return base
        if s0 != 0:
            return base                     # non-tenpai: byte-identical to c151
        return SpeedValue._pick_discard(self, hand, drawn, exposed, gangs, view=view)


class SpeedValueFan2(SpeedValue):
    """Dose escalation: double the tenpai value weights (live waits + fan).

    The fitted CI on the fan coefficient is wide (2.42 ~ 3.75 points) and the
    live-wait coefficient likewise (0.118 ~ 0.211); `SpeedValue` took the
    conservative end.  If the mechanism is real, a stronger dose should move the
    arena win endpoint further; if the effect collapses, the conservative end was
    already past the optimum.
    """

    W_LIVE_WAIT = 0.236
    W_MAX_FAN = 4.84

    def __init__(self, name="speedvaluefan2"):
        super().__init__(name)


class SpeedValuePenalty(SpeedValue):
    """Interpolation: keep a REDUCED pair penalty on top of the value model.

    c151 pays up to 8 live tiles (ROUTE_BONUS=8) to force pairs <= 2; route0
    removes it entirely.  On the arena, "remove it alone" is neutral (t=+0.03)
    while "remove it + value reordering" is strongly positive (t=-2.85), so the
    two changes interact.  This arm keeps a *quarter* of the original incentive
    (8 tiles x W_UKEIRE[1] = 0.64 points) to test whether the penalty is needed
    at all once the value terms are present.
    """

    PAIR_BONUS_POINTS = 0.64

    def __init__(self, name="speedvaluepenalty"):
        super().__init__(name)

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None:
            return None
        try:
            import collections as _c
            pc = sum(1 for n in _c.Counter(rem).values() if n >= 2)
        except Exception:
            return v
        if pc <= 2:
            v += self.PAIR_BONUS_POINTS
        return v


class SpeedValuePairKeep(SpeedValue):
    """The opposite sign on the pair axis: REWARD keeping 3+ pairs.

    R949 measured the leaders holding >=3 pairs at turn 7+ far more often than we
    do (25.2% vs 7.5%), and pairs are the only peng resource; on a tsumo-only
    board a peng removes two tiles you no longer have to draw yourself.
    `SpeedValue` already drops c151's pair penalty entirely; `SpeedValuePenalty`
    adds a fraction of it back and is *worse* on the arena (t=+1.14, n=457).
    This arm goes the other way and pays 0.64 points for 3+ pairs.
    """

    PAIR_REWARD_POINTS = 0.64

    def __init__(self, name="speedvaluepairkeep"):
        super().__init__(name)

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None:
            return None
        try:
            import collections as _c
            pc = sum(1 for n in _c.Counter(rem).values() if n >= 2)
        except Exception:
            return v
        if pc >= 3:
            v += self.PAIR_REWARD_POINTS
        return v
