# -*- coding: utf-8 -*-
"""One-step width lookahead on the production TUGC baseline.

This is a pure-lookahead candidate: it deliberately does not inherit the
c151 route-bonus chain, so it can be used when c151 fails the first-rate
guardrail.
"""
from __future__ import annotations

import collections
import time

from mahjong.shanten_exact import shanten as exact_shanten

from .c069routes import ukeire_counts
from .speed import _chi_pairs
from .speedc135 import _pref
from .speedc136 import _after_best, _state
from .speedgangfix import _pick_discard_route_gangaware
from .speedtugc import SpeedTUGC
from .ukeire import neigh_tiles, real_ukeire, visible_counts


class SpeedLookaheadTUGC(SpeedTUGC):
    LOOK_RIVER_MIN = 7
    LOOK_DEADLINE_MS = 250.0
    PARAMS = {1: (4, 0.20), 2: (8, 0.50)}
    PAIR_TOL = 0

    def __init__(self, name="speedlookaheadtugc"):
        super().__init__(name)

    @staticmethod
    def _topk_after_draw(h14, public, topk):
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
                        key=lambda x: (-ukeire_counts(x[2])[1], x[1]))[:topk]
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

    def _expected_lookahead(self, hand, public, total_live, tile, topk, deadline=None):
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
            if live > 0:
                draws.append((live, draw))
        draws.sort(key=lambda x: (-x[0], x[1]))
        draws = draws[:10]
        for live, draw in draws:
            if deadline is not None and time.monotonic() >= deadline:
                return None, None
            value = self._topk_after_draw(list(h13) + [draw], public, topk)
            if deadline is not None and time.monotonic() >= deadline:
                return None, None
            if value is None:
                continue
            useful_live += live
            weighted += live * value
        non_useful = max(0, total_live - useful_live)
        return (weighted + non_useful * current) / float(total_live), current

    @staticmethod
    def _pair_count(hand):
        c = collections.Counter(hand)
        return sum(1 for v in c.values() if v >= 2)

    def _min_shanten(self, hand):
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
        return smin

    def _score_target(self, hand, public, total_live, target, topk, deadline=None):
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
            if s != target:
                continue
            expected, current = self._expected_lookahead(
                hand, public, total_live, d, topk, deadline=deadline)
            if expected is None:
                if deadline is not None and time.monotonic() >= deadline:
                    return None
                continue
            scored.append((d, expected, current))
        return scored

    @staticmethod
    def _melds_info(view):
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        return e, g

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if gangs:
            return _pick_discard_route_gangaware(
                hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
                route_bonus=0.0, gate_river=0)
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
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
        scored = self._score_target(hand, public, total_live, target, topk, deadline)
        if not scored or len(scored) < 2:
            return base
        base_row = next((x for x in scored if x[0] == base), None)
        if base_row is None:
            return base
        base_pairs = self._pair_count([t for t in hand if t != base])
        allowed = [x for x in scored
                   if self._pair_count([t for t in hand if t != x[0]]) >= base_pairs - self.PAIR_TOL]
        if not allowed:
            return base
        best = max(allowed, key=lambda x: (x[1], -_pref(x[0], hand),
                                           -1 if x[0] == drawn else 0, x[0]))
        if best[0] == base or best[1] - base_row[1] < margin:
            return base
        return best[0]

    def _want_claim(self, view, kind, pair=None):
        e, g = self._melds_info(view)
        if not g:
            return super()._want_claim(view, kind, pair)
        if kind not in ("chi", "peng"):
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        if not offer or len(hand) != 13 - 3 * e:
            return False
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            vis = None
        before = _state(hand, e, 0, vis, self.GOD_MELD)
        if before is None or before[1] is None:
            return False
        if kind == "chi":
            opts = [("chi", p) for p in _chi_pairs(hand, offer)]
            if pair is not None:
                opts = [("chi", pair)]
        else:
            opts = [("peng", None)]
        for k, p in opts:
            after = _after_best(hand, offer, k, p, e, 0, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] < before[0]:
                return True
            if after[0] == before[0] and (after[1] or 0.0) > (before[1] or 0.0):
                return True
        return False

    def decide(self, view):
        try:
            phase = str(view.get("phase") or "")
            e, g = self._melds_info(view)
        except Exception:
            return super().decide(view)
        if not g or not phase.startswith("response_"):
            return super().decide(view)
        hand = list(view.get("my_hand") or [])
        offer = view.get("offer_tile")
        if len(hand) != 13 - 3 * e or not offer:
            return {"action": "pass", "tile": ""}
        if phase == "response_peng":
            cnt = hand.count(offer)
            if cnt >= 3 and self._want_claim(view, "gang_ming"):
                return {"action": "gang", "tile": offer}
            if cnt >= 2 and self._want_claim(view, "peng"):
                return {"action": "peng", "tile": offer}
            return {"action": "pass", "tile": ""}
        if phase == "response_chi":
            chi_cnt = sum(1 for m in (view.get("melds") or [])
                          if isinstance(m, dict) and m.get("type") == "chi")
            if chi_cnt < 2:
                for pair in _chi_pairs(hand, offer):
                    if self._want_claim(view, "chi", pair):
                        return {"action": "chi", "tile": offer}
            return {"action": "pass", "tile": ""}
        return super().decide(view)
