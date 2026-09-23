# -*- coding: utf-8 -*-
# Smart gang acceptance: take the ming-gang only when it does NOT leave the hand
# worse (post-gang best shanten <= pre-gang shanten).
#
# Rationale: R1025 measured that the gang arm's gain is TEMPO (hu_rate +1.5pp,
# tenpai_rate +1.1pp, fan/win unchanged).  But the unconditional arm also accepts
# gangs that break a wait -- which would cost tempo, the very thing being bought.
# This variant keeps the wall guard and the P0 discard fix, and additionally
# rejects a gang that raises shanten.
from __future__ import annotations

from .speedc136 import _after_best, _state
from .speedgangtakefixed import SpeedGangTakeFixed
from .ukeire import visible_counts


class SpeedGangTakeSmart(SpeedGangTakeFixed):
    def __init__(self, name="speedgangtakesmart"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if kind == "gang_ming":
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            e = len(melds)
            g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
            offer = view.get("offer_tile")
            if not offer:
                return False
            if len(view.get("river") or []) >= int(self.SELF_GANG_MAX_RIVER):
                return False
            try:
                vis = visible_counts(hand, river=view.get("river"),
                                     all_melds=view.get("all_melds"))
                before = _state(hand, e, g, vis, self.GOD_MELD)
                after = _after_best(hand, offer, "gang_ming", None, e, g, vis, self.GOD_MELD)
            except Exception:
                return True
            if (before and after and before[0] is not None and after[0] is not None):
                return after[0] <= before[0]
            return True
        return super()._want_claim(view, kind, pair)
