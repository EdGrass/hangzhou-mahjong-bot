# -*- coding: utf-8 -*-
"""Keep the promise the claim gate made: play the post-meld discard it assumed.

`speedc136` / `speedc151` accept a chi/peng/ming-gang when the BEST legal discard
afterwards beats the pre-claim hand:

    after_best = min over d of (shanten(H-d), -real_ukeire(H-d))

But that is an assumption about the NEXT decision.  The normal discard chooser
also carries route bonuses, pair-count preferences, keep-white rules and `_pref`
tie-breaks, so it sometimes plays a different tile and throws the gain away.

Real portal replays (`var/_postmeld_discard_gap.py`, 900 files / 7200 rounds,
only claims where the actual discard is inside the gate's candidate table):

    cohort   evaluable   plays argmax   deviates   mean ukeire lost   loses >=5
    我方        6316        89.4%         10.6%          4.29            3.0%
    top32      9186        95.6%          4.4%          3.12            0.8%
    其他      13418        93.4%          6.6%          5.32            2.4%

We deviate 2.4x as often as the strong players and our deviations cost more.
This arm removes exactly that inconsistency and changes nothing else: the first
discard after one of our own claims is chosen by the same key the gate used.
Every other decision is delegated to `SpeedC151` byte-for-byte.

Detection: after a claim the hand is 14-3e-g tiles with no drawn tile (the
claimed tile plays the role of the draw).  The dealer's opening discard also has
no drawn tile but has e=0, so it is excluded.
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc136 import _state
from .speedc151 import SpeedC151
from .ukeire import visible_counts


class SpeedMeldPost(SpeedC151):
    def __init__(self, name="speedmeldpost"):
        super().__init__(name)

    def post_claim_discard(self, hand, exposed, gangs, view):
        """The gate's own criterion, returning the tile instead of only its value."""
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            return None
        best = None
        for d in sorted(set(hand)):
            h3 = list(hand)
            h3.remove(d)
            if len(h3) != 13 - 3 * exposed - gangs:
                continue
            st = _state(h3, exposed, gangs, vis, self.GOD_MELD)
            if st is None:
                continue
            # `_state` returns (0, None) for a completed/tenpai shape; that is the
            # BEST outcome, not a missing value (the claim gate scores it the same
            # way: `k = (st[0], -(st[1] or 0))`).
            k = (st[0], -(st[1] or 0))
            if best is None or k < best[0]:
                best = (k, d)
        return best[1] if best else None

    def claim_key(self, hand, tile, exposed, gangs, view):
        """The claim gate's score for playing `tile` from `hand`."""
        if tile not in hand:
            return None
        h3 = list(hand)
        h3.remove(tile)
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            return None
        st = _state(h3, exposed, gangs, vis, self.GOD_MELD)
        if st is None:
            return None
        return (st[0], -(st[1] or 0))

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        # Only the FIRST discard after one of our own claims is in scope: hand is
        # 14-3e-g tiles and no tile was drawn (the claim plays the draw's role).
        if not (view and drawn is None and exposed >= 1 and hand
                and len(hand) == 14 - 3 * exposed - gangs):
            return base
        cand = self.post_claim_discard(hand, exposed, gangs, view)
        if cand is None or cand == base or cand not in hand:
            return base
        # Override ONLY when the gate's own criterion is STRICTLY better: ties
        # keep the production chooser's tuned `_pref` tie-break untouched.
        kc = self.claim_key(hand, cand, exposed, gangs, view)
        kb = self.claim_key(hand, base, exposed, gangs, view)
        if kc is not None and kb is not None and kc < kb:
            return cand
        return base
