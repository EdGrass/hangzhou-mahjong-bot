# -*- coding: utf-8 -*-
"""Mixin: gate the 吃 decision on the pair the PLATFORM will actually use.

Evidence (this session, real replays of the running campaign):
  * 吃 is legal only from the upstream seat (delta==1): 6873/6873 chi events.
  * our chi action carries no tile pair, so the platform picks; measured on 1168
    graded multi-option chi events the platform ALWAYS picks the LAST legal option
    (present options {1,2}->2, {0,1}->1, {0,1,2}->2) in the canonical order
    ((n-2,n-1), (n-1,n+1), (n+1,n+2)).
  * with that default the realised pair is worse than the best option in 15.1% of
    those events, but worse than the PRE-claim state in only 0.2% (2/1168).

The inherited gate (`want_claim_mild`) is pair-agnostic: for a non-tenpai hand it
takes `min` over ALL legal pairs, so it accepts a claim even when the pair the
platform will use is the bad one.  `tests/test_speedmeldmore.py` catches exactly
that (boundedness violation).  This mixin evaluates the bounded rule on the
realised pair only, which (a) restores the documented contract and (b) makes the
arm's accept set consistent with what the server will do.

Rule implemented (same as C136 + SpeedMeldMore0, but pair-exact):
  * before > 0 : accept iff (s_after < before) or (s_after == before and
                 live_after >= live_before)
  * before == 0: accept iff s_after == 0 and waits_after > waits_before
  * never accept a pair that raises the shanten.
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speed import _chi_pairs
from .speedc151 import SpeedC151
from .speedc136 import _state
from .ukeire import real_ukeire, visible_counts


def platform_chi_pair(hand, offer):
    """The pair the platform uses: the LAST legal option in canonical order."""
    opts = _chi_pairs(hand, offer)
    return opts[-1] if opts else None


def _after_pair(hand, offer, pair, e, g, vis, god_meld=True):
    """(best shanten after the mandatory discard, its live ukeire, its waits count)."""
    h2 = list(hand)
    try:
        for x in pair:
            h2.remove(x)
    except ValueError:
        return None
    e2, g2 = e + 1, g
    best = None
    for d in sorted(set(h2)):
        h3 = list(h2)
        h3.remove(d)
        if len(h3) != 13 - 3 * e2 - g2:
            continue
        try:
            s = exact_shanten(h3, qidui=(e2 == 0 and g2 == 0),
                              exposed_melds=e2, gangs=g2, god_meld=god_meld)
        except Exception:
            continue
        if s == 0:
            u, w = 0.0, len(waits(h3, exposed_melds=e2, gangs=g2))
        else:
            try:
                uu = real_ukeire(h3, exposed=e2, gangs=g2, visible=vis,
                                 god_meld=god_meld)[0]
            except Exception:
                uu = None
            u, w = (float(uu or 0.0), 0)
        key = (s, -u, -w)
        if best is None or key < best[0]:
            best = (key, s, u, w)
    if best is None:
        return None
    return best[1], best[2], best[3]


class ChiRealizedMixin:
    """Override only the 吃 branch of `_want_claim`; 碰/杠 delegate to the chain."""

    def _want_claim(self, view, kind, pair=None):
        if kind != "chi":
            return super()._want_claim(view, kind, pair)
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        if sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "chi") >= 2:
            return False
        p = platform_chi_pair(hand, offer)
        if p is None:
            return False
        # `decide()` asks once per legal pair with the SAME view object; the verdict
        # only depends on the realised pair, so compute it once per window.
        cache_key = "_chi_realized_verdict"
        cached = view.get(cache_key)
        if cached is not None and cached[0] == offer:
            return cached[1]
        vis = visible_counts(hand, river=view.get("river"),
                             all_melds=view.get("all_melds"))
        before = _state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[0] is None:
            return False
        after = _after_pair(hand, offer, p, e, g, vis, self.GOD_MELD)
        if after is None:
            return False
        s_before, u_before = before[0], before[1]
        s_after, u_after, w_after = after
        if s_before == 0:
            try:
                w_before = len(waits(hand, exposed_melds=e, gangs=g))
            except Exception:
                verdict = False
            else:
                verdict = bool(s_after == 0 and w_after > w_before)
        elif s_after < s_before:
            verdict = True
        elif s_after == s_before and u_before is not None and u_after >= u_before:
            verdict = True
        else:
            verdict = False
        view[cache_key] = (offer, verdict)
        return verdict


class SpeedChiRealized(ChiRealizedMixin, SpeedC151):
    """c151 + realised-pair 吃 gate (new arm; not registered during the campaign)."""

    def __init__(self, name="speedchirealized"):
        super().__init__(name)


from .speedmeldmore import SpeedMeldMore0        # noqa: E402  (after the mixin)


class SpeedMeldMore0Chi(ChiRealizedMixin, SpeedMeldMore0):
    """Campaign-3 candidate: the bounded meld relaxation, with the 吃 branch made
    pair-exact.

    * 碰 : inherited from `SpeedMeldMore0` (accept equal-shanten melds whose live
      ukeire does not drop; never accept a worse shanten).
    * 吃 : same rule, but evaluated on the pair the platform will actually use
      (the last legal option) instead of "any legal pair" -- this is what makes
      the arm's accept set equal to its realised effect, and what repairs the
      boundedness violation found in `tests/test_speedmeldmore.py`.
    """
    TOL = 0.0

    def __init__(self, name="speedmeldmore0chi"):
        super().__init__(name)
