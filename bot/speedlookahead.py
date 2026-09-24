# -*- coding: utf-8 -*-
"""SpeedLookahead -- one-step width lookahead on top of SpeedStack.

Evidence (R963 probes):
  - 41-44% of real 1-shanten decisions have a candidate that is worse in
    current real_ukeire but better in expected next-step width.
  - Exact expected lookahead gains +0.9 live on those decisions, while the
    current greedy choice loses about 4 live immediately.
  - Top-K pruning at K=4 preserves most of the gain at a fraction of the cost.

Scope is deliberately narrow:
  - no exposed melds and no gangs;
  - only minimum shanten == 1;
  - only after the public river reaches LOOK_RIVER_MIN.
All other decisions are delegated byte-for-byte to SpeedStack.
"""
from __future__ import annotations

import collections
import time

from mahjong.shanten_exact import shanten as exact_shanten

from .c069routes import ukeire_counts
from .speedc135 import _pref
from .speedstack import SpeedStack
from .ukeire import neigh_tiles, real_ukeire, visible_counts


class SpeedLookahead(SpeedStack):
    TARGET_SHANTEN = 1
    LOOK_RIVER_MIN = 7
    TOP_K = 4
    TOP_DRAWS = 10
    SWITCH_MARGIN = 0.20
    LOOK_DEADLINE_MS = 250.0

    def __init__(self, name="speedlookahead"):
        super().__init__(name)

    @staticmethod
    def _topk_after_draw(h14, public, k):
        cands = []
        for d in sorted(set(h14)):
            h13 = list(h14)
            h13.remove(d)
            try:
                s = exact_shanten(h13, qidui=True, exposed_melds=0, gangs=0)
            except Exception:
                continue
            cands.append((s, d, h13))
        if not cands:
            return None
        smin = min(c[0] for c in cands)
        ranked = sorted((c for c in cands if c[0] == smin),
                        key=lambda x: (-ukeire_counts(x[2])[1], x[1]))[:k]
        best = None
        for _s, _d, h13 in ranked:
            vv = collections.Counter(public)
            vv.update(h14)
            try:
                live = real_ukeire(h13, exposed=0, gangs=0, visible=vv)[0]
            except Exception:
                continue
            if live is not None and (best is None or live > best):
                best = live
        return best

    def _expected_lookahead(self, hand, public, total_live, tile, deadline=None):
        h13 = list(hand)
        h13.remove(tile)
        before = collections.Counter(h13)
        before[tile] += 1
        vv = collections.Counter(public)
        vv.update(h13)
        vv[tile] += 1
        try:
            current = real_ukeire(h13, exposed=0, gangs=0, visible=vv)[0]
        except Exception:
            return None, None
        if current is None:
            return None, None
        weighted = 0.0
        useful_live = 0
        if deadline is not None and time.monotonic() >= deadline:
            return None, None
        draws = []
        for draw in neigh_tiles(h13):
            live = 4 - int(public.get(draw, 0)) - int(before.get(draw, 0))
            if live <= 0:
                continue
            draws.append((live, draw))
        draws.sort(key=lambda x: (-x[0], x[1]))
        draws = draws[:self.TOP_DRAWS]
        for live, draw in draws:
            if deadline is not None and time.monotonic() >= deadline:
                return None, None
            h14 = list(h13) + [draw]
            value = self._topk_after_draw(h14, public, self.TOP_K)
            if deadline is not None and time.monotonic() >= deadline:
                return None, None
            if value is None:
                continue
            useful_live += live
            weighted += live * value
        non_useful = max(0, total_live - useful_live)
        expected = (weighted + non_useful * current) / float(total_live)
        return expected, current

    def _score_candidates(self, hand, public, total_live, deadline=None):
        """Return [(tile, expected_next_width, current_width), ...]."""
        scored = []
        for d in sorted(set(hand)):
            if deadline is not None and time.monotonic() >= deadline:
                return None
            h13 = list(hand)
            h13.remove(d)
            try:
                s = exact_shanten(h13, qidui=True, exposed_melds=0, gangs=0)
            except Exception:
                continue
            if s != self.TARGET_SHANTEN:
                continue
            expected, current = self._expected_lookahead(
                hand, public, total_live, d, deadline=deadline)
            if expected is None:
                if deadline is not None and time.monotonic() >= deadline:
                    return None
                continue
            scored.append((d, expected, current))
        return scored

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        if exposed or gangs or not view:
            return base
        river_len = len(view.get("river") or [])
        if river_len < self.LOOK_RIVER_MIN:
            return base
        public = visible_counts([], river=view.get("river"),
                                all_melds=view.get("all_melds"))
        total_live = 136 - sum(int(x) for x in public.values()) - len(hand)
        if total_live <= 0:
            return base
        deadline = (time.monotonic() + self.LOOK_DEADLINE_MS / 1000.0
                    if self.LOOK_DEADLINE_MS and self.LOOK_DEADLINE_MS > 0 else None)
        scored = self._score_candidates(hand, public, total_live, deadline=deadline)
        if not scored or len(scored) < 2:
            return base
        best = max(scored, key=lambda x: (x[1], -_pref(x[0], hand),
                                          -1 if x[0] == drawn else 0, x[0]))
        base_row = next((x for x in scored if x[0] == base), None)
        if base_row is None:
            return base
        if best[0] == base or best[1] - base_row[1] < self.SWITCH_MARGIN:
            return base
        return best[0]


class SpeedLookahead2(SpeedLookahead):
    """s=2 one-step width lookahead (K=8, stricter margin)."""

    TARGET_SHANTEN = 2
    TOP_K = 8
    SWITCH_MARGIN = 0.50

    def __init__(self, name="speedlookahead2"):
        super().__init__(name)


class SpeedLookaheadBoth(SpeedStack):
    """Apply s=1 lookahead on 1-shanten and s=2 lookahead on 2-shanten."""

    def __init__(self, name="speedlookaheadboth"):
        super().__init__(name)
        self._p1 = SpeedLookahead()
        self._p2 = SpeedLookahead2()

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if exposed or gangs or not view or len(hand) != 14:
            return super()._pick_discard(hand, drawn, exposed, gangs, view=view)
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
        return super()._pick_discard(hand, drawn, exposed, gangs, view=view)

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
