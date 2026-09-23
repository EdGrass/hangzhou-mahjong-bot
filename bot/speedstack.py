# -*- coding: utf-8 -*-
"""SpeedStack -- compose independently bounded improvements on top of c151.

Components (all only affect decisions where the base policy is still valid):
  1. SpeedGangFixLate: gang-aware hand math (P0 fix) + late-gated pair bonus.
  2. c230 semantics: when several chi pairs pass the parent gate, choose the
     pair with the best (shanten, -real_ukeire) result instead of the first.
  3. speedtenpailivefan semantics: when already tenpai, switch only to a
     discard with strictly more live wait tiles, and only if max fan does not
     decrease.

This class is intentionally not registered in run_bot.py.  It can be used by
dotted class path for smoke/concurrency checks, and registered only after the
active campaign has ended.
"""
from __future__ import annotations

from mahjong.fan import calc as calc_fan
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speed import _chi_pairs
from .speedc136 import _after_best
from .speedgangfix import SpeedGangFixLate
from .ukeire import visible_counts


class SpeedStack(SpeedGangFixLate):
    def __init__(self, name="speedstack"):
        super().__init__(name)

    @staticmethod
    def _live_wait_count(hand13, exposed, vis):
        try:
            ws = waits(hand13, exposed_melds=exposed, gangs=0)
        except Exception:
            return None
        if not ws:
            return 0
        total = 0
        for t in ws:
            total += max(0, 4 - int((vis or {}).get(t, 0)))
        return total

    @staticmethod
    def _max_fan(rem13, exposed, view):
        try:
            ws = waits(rem13, exposed_melds=exposed, gangs=0)
        except Exception:
            return None
        god = (view or {}).get("god") or {}
        chain = {
            "count": int(god.get("chain_count") or 0),
            "piao": int(god.get("piao_count") or 0),
        }
        best = None
        for wt in (ws or []):
            try:
                result = calc_fan(list(rem13), wt, chain, base=1,
                                  exposed_melds=exposed, gangs=0)
            except Exception:
                continue
            if result.get("hu"):
                fan = result.get("fan") or 0
                if best is None or fan > best:
                    best = fan
        return best

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        if not base or base not in hand or gangs:
            return base
        if len(hand) != 14 - 3 * exposed:
            return base
        vis = None
        if view:
            try:
                vis = visible_counts(hand, river=view.get("river"),
                                     all_melds=view.get("all_melds"))
            except Exception:
                vis = None
        if vis is None:
            return base
        try:
            rem0 = list(hand)
            rem0.remove(base)
            s0 = exact_shanten(rem0, qidui=(exposed == 0),
                               exposed_melds=exposed, gangs=0,
                               god_meld=self.GOD_MELD)
        except Exception:
            return base
        if s0 != 0:
            return base
        live0 = self._live_wait_count(rem0, exposed, vis)
        if live0 is None:
            return base
        best_tile, best_live = base, live0
        fan0 = self._max_fan(rem0, exposed, view)
        for d in sorted(set(hand)):
            if d == base:
                continue
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0),
                                  exposed_melds=exposed, gangs=0,
                                  god_meld=self.GOD_MELD)
            except Exception:
                continue
            if s != 0:
                continue
            live = self._live_wait_count(rem, exposed, vis)
            if live is None or live <= best_live:
                continue
            if fan0 is not None:
                fan = self._max_fan(rem, exposed, view)
                if fan is not None and fan < fan0:
                    continue
            best_tile, best_live = d, live
        return best_tile

    def _want_claim(self, view, kind, pair=None):
        if kind != "chi" or pair is None:
            return super()._want_claim(view, kind, pair)
        # Delegate the actual gate first; this keeps c151/C136/C144 semantics.
        if not super()._want_claim(view, kind, pair):
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds
                    if isinstance(m, dict) and m.get("type") == "gang")
        if not offer:
            return True
        pairs = _chi_pairs(hand, offer)
        if len(pairs) < 2:
            return True
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            return True
        best_pair = None
        best_key = None
        for p in pairs:
            if not super()._want_claim(view, "chi", p):
                continue
            after = _after_best(hand, offer, "chi", p, exposed, 0,
                                vis, self.GOD_MELD)
            if after is None:
                key = (99, 0.0)
            else:
                key = (after[0], -(after[1] or 0.0))
            pt = tuple(p)
            if best_key is None or key < best_key:
                best_key, best_pair = key, pt
        if best_pair is None:
            return True
        return tuple(pair) == best_pair
