# -*- coding: utf-8 -*-
"""Anytime (partial-result) one-step width lookahead.

Motivation -- measured defect in `SpeedLookahead` / `SpeedLookahead2` (R974):

The parent `_score_candidates` / `_score_target` return **None for the whole
decision** as soon as the global deadline fires, so `_pick_discard` silently
falls back to the base policy.  The inner `_expected_lookahead` already returns
`(None, None)` per candidate on timeout, i.e. the information needed for a
partial decision exists -- the parent simply throws it away.

Production-shaped (cache-cold) replay measurements over recent auto rooms
(`var/_lookahead_coldreact.py`, 2026-09-18+ replays, river>=7, zero melds):

    arm               cold change-rate   warm change-rate   lost signal
    speedlookahead        13.0% (39/300)      17.0% (51/300)   ~24%
    speedlookahead2        2.0% ( 1/50)       18.0% ( 9/50)   ~89%

(`shanten_exact` memoises decompositions, so a warm second call on the SAME
hand is 5-10x faster -- earlier latency evidence that measured a warm repeat
therefore under-reported the production cost.)

What this module changes -- nothing else:

1. **Fair per-candidate budget.**  Instead of one global deadline that the scan
   runs into after 3-5 candidates, every candidate gets an equal slice of the
   remaining budget (`PER_CANDIDATE_FLOOR_MS` .. `PER_CANDIDATE_MS`).
2. **Base-first ordering.**  The candidate that the base policy would discard is
   scored FIRST, with an extra-large slice.  `_pick_discard` requires `base` to
   be present in the scored list (otherwise it returns base anyway), so without
   this the recovered signal would often still be unusable.
3. **Partial results instead of None.**  A scan that ran out of budget returns
   whatever it scored (>= 2 entries to be usable), never `None`.

Safety: `_pick_discard` in the parent already handles a missing/short list by
returning `base`, and every score kept here is a genuine full
`_expected_lookahead` value -- no value is ever approximated or fabricated.
The switch rule, margins, river gate and scope are inherited unchanged.
"""
from __future__ import annotations

import time

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc135 import _pref
from .speedlookahead import SpeedLookahead, SpeedLookahead2, SpeedLookaheadBoth
from .speedlookahead_tugc import SpeedLookaheadTUGC
from .speedstack import SpeedStack


class _AnytimeBudget:
    """Equal-slice, base-first budget policy shared by all variants."""

    PER_CANDIDATE_MS = 200.0       # cap for a single candidate
    PER_CANDIDATE_FLOOR_MS = 18.0  # never hand out less than this
    BASE_SLICE_FRACTION = 0.40     # share of the budget reserved for `base`
    MIN_USABLE = 2                 # _pick_discard needs >= 2 scored rows

    @classmethod
    def _slice_deadline(cls, now, deadline, remaining, is_base):
        """Deadline for the next candidate.

        `deadline` is the *global* budget end handed down by `_pick_discard`.
        We hand each candidate an equal share of whatever is left, with `base`
        getting a reserved fraction so it is (almost) always scored.
        """
        cap = cls.PER_CANDIDATE_MS / 1000.0
        floor = cls.PER_CANDIDATE_FLOOR_MS / 1000.0
        if deadline is None:
            return now + cap
        room = deadline - now
        if room <= 0:
            return now
        if is_base:
            share = room * cls.BASE_SLICE_FRACTION
        else:
            share = room / float(max(1, remaining))
        return now + max(floor, min(cap, share))

    def _candidate_order(self, hand, base, cands=None):
        """`base` first, then the remaining candidates (stable order).

        `cands` (the in-scope set) is used when supplied so the budget is split
        across scoreable candidates only.
        """
        ds = sorted(cands) if cands is not None else sorted(set(hand))
        if base is not None and base in ds:
            ds.remove(base)
            return [base] + ds
        return ds


class SpeedLookaheadAnytime(_AnytimeBudget, SpeedLookahead):
    """s=1 lookahead that degrades gracefully instead of going inert."""

    def __init__(self, name="speedlookaheadanytime"):
        super().__init__(name)

    def _in_scope(self, hand, target):
        """Discards whose 13-tile remainder keeps `target` shanten.

        Cheaper than the lookahead by ~50x, so we pay it up front and then split
        the budget across the candidates that can actually be scored -- the
        first version divided the budget by *every* distinct tile and starved
        most real candidates (42% of positions produced no usable row).
        """
        out = []
        for d in sorted(set(hand)):
            h13 = list(hand)
            h13.remove(d)
            try:
                s = exact_shanten(h13, qidui=True, exposed_melds=0, gangs=0)
            except Exception:
                continue
            if s == target:
                out.append(d)
        return out

    def _score_candidates(self, hand, public, total_live, deadline=None, base=None):
        order = self._candidate_order(hand, base, self._in_scope(hand, self.TARGET_SHANTEN))
        scored = []
        for i, d in enumerate(order):
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                break
            cand_dl = self._slice_deadline(now, deadline, len(order) - i, d == base)
            expected, current = self._expected_lookahead(
                hand, public, total_live, d, deadline=cand_dl)
            if expected is None:
                continue
            scored.append((d, expected, current))
            if (deadline is not None and time.monotonic() >= deadline
                    and len(scored) >= self.MIN_USABLE):
                break
        return scored

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = SpeedStack._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        if exposed or gangs or not view or len(hand) != 14:
            return base
        river_len = len(view.get("river") or [])
        if river_len < self.LOOK_RIVER_MIN:
            return base
        from .ukeire import visible_counts
        public = visible_counts([], river=view.get("river"),
                                all_melds=view.get("all_melds"))
        total_live = 136 - sum(int(x) for x in public.values()) - len(hand)
        if total_live <= 0:
            return base
        deadline = (time.monotonic() + self.LOOK_DEADLINE_MS / 1000.0
                    if self.LOOK_DEADLINE_MS and self.LOOK_DEADLINE_MS > 0 else None)
        scored = self._score_candidates(hand, public, total_live,
                                        deadline=deadline, base=base)
        if not scored or len(scored) < self.MIN_USABLE:
            return base
        best = max(scored, key=lambda x: (x[1], -_pref(x[0], hand),
                                          -1 if x[0] == drawn else 0, x[0]))
        base_row = next((x for x in scored if x[0] == base), None)
        if base_row is None:
            return base
        if best[0] == base or best[1] - base_row[1] < self.SWITCH_MARGIN:
            return base
        return best[0]


class SpeedLookaheadAnytime2(SpeedLookaheadAnytime):
    """s=2 variant: same anytime policy, K=8 / margin 0.5 as the parent."""

    TARGET_SHANTEN = 2
    TOP_K = 8
    SWITCH_MARGIN = 0.50

    def __init__(self, name="speedlookaheadanytime2"):
        super().__init__(name)


class SpeedLookaheadAnytimeBoth(SpeedLookaheadBoth):
    """s=1 on 1-shanten and s=2 on 2-shanten, both anytime."""

    #: sub-policies inherit this budget; None == leave the 250 ms default alone
    LOOK_DEADLINE_MS = None

    def __init__(self, name="speedlookaheadanytimeboth"):
        SpeedStack.__init__(self, name)
        self._p1 = SpeedLookaheadAnytime()
        self._p2 = SpeedLookaheadAnytime2()
        if self.LOOK_DEADLINE_MS is not None:
            self._p1.LOOK_DEADLINE_MS = float(self.LOOK_DEADLINE_MS)
            self._p2.LOOK_DEADLINE_MS = float(self.LOOK_DEADLINE_MS)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if exposed or gangs or not view or len(hand) != 14:
            return SpeedStack._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        smin = None
        for d in sorted(set(hand)):
            h13 = list(hand)
            h13.remove(d)
            try:
                s = exact_shanten(h13, qidui=True, exposed_melds=0, gangs=0)
            except Exception:
                continue
            if smin is None or s < smin:
                smin = s
        if smin == 1:
            return self._p1._pick_discard(hand, drawn, exposed, gangs, view=view)
        if smin == 2:
            return self._p2._pick_discard(hand, drawn, exposed, gangs, view=view)
        return SpeedStack._pick_discard(self, hand, drawn, exposed, gangs, view=view)

    def _score_candidates(self, hand, public, total_live, deadline=None):
        smin = None
        for d in sorted(set(hand)):
            h13 = list(hand)
            h13.remove(d)
            try:
                s = exact_shanten(h13, qidui=True, exposed_melds=0, gangs=0)
            except Exception:
                continue
            if smin is None or s < smin:
                smin = s
        if smin == 1:
            return self._p1._score_candidates(hand, public, total_live, deadline=deadline)
        if smin == 2:
            return self._p2._score_candidates(hand, public, total_live, deadline=deadline)
        return []


class SpeedLookaheadAnytimeTUGC(_AnytimeBudget, SpeedLookaheadTUGC):
    """TUGC-baseline variant (used when the c151 chain fails the 1st-rate gate)."""

    def __init__(self, name="speedlookaheadanytimetugc"):
        super().__init__(name)

    def _score_target(self, hand, public, total_live, target, topk,
                      deadline=None, base=None):
        order = self._candidate_order(hand, base, self._in_scope(hand, target))
        scored = []
        for i, d in enumerate(order):
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                break
            cand_dl = self._slice_deadline(now, deadline, len(order) - i, d == base)
            expected, current = self._expected_lookahead(
                hand, public, total_live, d, topk, deadline=cand_dl)
            if expected is None:
                continue
            scored.append((d, expected, current))
            if (deadline is not None and time.monotonic() >= deadline
                    and len(scored) >= self.MIN_USABLE):
                break
        return scored

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        from .speedgangfix import _pick_discard_route_gangaware
        from .ukeire import visible_counts
        if gangs:
            return _pick_discard_route_gangaware(
                hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
                route_bonus=0.0, gate_river=0)
        base = SpeedStack._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        if exposed or gangs or not view or len(hand) != 14:
            return base
        if len(view.get("river") or []) < self.LOOK_RIVER_MIN:
            return base
        public = visible_counts([], river=view.get("river"),
                                all_melds=view.get("all_melds"))
        total_live = 136 - sum(int(x) for x in public.values()) - len(hand)
        if total_live <= 0:
            return base
        target = self._min_shanten(hand)
        if target not in self.PARAMS:
            return base
        topk, margin = self.PARAMS[target]
        deadline = (time.monotonic() + self.LOOK_DEADLINE_MS / 1000.0
                    if self.LOOK_DEADLINE_MS > 0 else None)
        scored = self._score_target(hand, public, total_live, target, topk,
                                    deadline, base=base)
        if not scored or len(scored) < self.MIN_USABLE:
            return base
        base_row = next((x for x in scored if x[0] == base), None)
        if base_row is None:
            return base
        base_pairs = self._pair_count([t for t in hand if t != base])
        allowed = [x for x in scored
                   if self._pair_count([t for t in hand if t != x[0]])
                   >= base_pairs - self.PAIR_TOL]
        if not allowed:
            return base
        best = max(allowed, key=lambda x: (x[1], -_pref(x[0], hand),
                                           -1 if x[0] == drawn else 0, x[0]))
        if best[0] == base or best[1] - base_row[1] < margin:
            return base
        return best[0]


class SpeedLookaheadLongBoth(SpeedLookaheadAnytimeBoth):
    """s1+s2 anytime with a 900 ms budget (server move window is 3000 ms).

    The 250 ms budget inherited from the parents was chosen when latency had
    only ever been measured on a WARM shanten cache (see the module docstring);
    cold full scans cost p50 ~170 ms / p90 ~500 ms for s1 and p50 ~420 ms /
    p90 ~900 ms for s2, so 250 ms truncates a large share of them.
    """

    LOOK_DEADLINE_MS = 900.0

    def __init__(self, name="speedlookaheadlongboth"):
        super().__init__(name)


class SpeedLookaheadNoDeadlineBoth(SpeedLookaheadAnytimeBoth):
    """Diagnostic ceiling: same mechanism with the deadline disabled.

    Not a production candidate -- this exists so the EV instrument can measure
    exactly how much signal the deadline is throwing away.
    """

    LOOK_DEADLINE_MS = 0.0

    def __init__(self, name="speedlookaheadnodeadlineboth"):
        super().__init__(name)


class SpeedLookaheadLong2(SpeedLookaheadAnytime2):
    """s=2 only, 900 ms budget."""

    LOOK_DEADLINE_MS = 900.0

    def __init__(self, name="speedlookaheadlong2"):
        super().__init__(name)


class SpeedLookaheadLong(SpeedLookaheadAnytime):
    """s=1 only, 900 ms budget."""

    LOOK_DEADLINE_MS = 900.0

    def __init__(self, name="speedlookaheadlong"):
        super().__init__(name)


class SpeedLookaheadLongTUGC(SpeedLookaheadAnytimeTUGC):
    """TUGC-baseline anytime lookahead with a 900 ms budget."""

    LOOK_DEADLINE_MS = 900.0

    def __init__(self, name="speedlookaheadlongtugc"):
        super().__init__(name)


class SpeedLookaheadAnytimeTUGC250(SpeedLookaheadAnytimeTUGC):
    """Explicit 250 ms TUGC variant (kept for ablations)."""

    LOOK_DEADLINE_MS = 250.0

    def __init__(self, name="speedlookaheadanytimetugc250"):
        super().__init__(name)
