# -*- coding: utf-8 -*-
"""Parametric C136 meld-gain gate for offline calibration."""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc151 import SpeedC151
from .speedtugc import want_claim_strict_meld
from .ukeire import visible_counts


class _MeldGainBase(SpeedC151):
    MIN_GAIN = 1
    KEEP_WHITE = False

    def _want_claim(self, view, kind, pair=None):
        if want_claim_strict_meld(view, kind, pair):
            return True
        if kind not in ("chi", "peng"):
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
        before = _state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[1] is None:
            return False
        opts = ([("chi", p) for p in _chi_pairs(hand, offer)] if kind == "chi"
                else [("peng", None)])
        for k, p in opts:
            used = list(p) if k == "chi" else [offer, offer]
            if self.KEEP_WHITE and "白" in used:
                continue
            after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] < before[0]:
                return True
            if after[0] == before[0] and (after[1] or 0.0) >= (before[1] or 0.0) + self.MIN_GAIN:
                return True
        return False


class SpeedMeldGain1(_MeldGainBase):
    MIN_GAIN = 1
    def __init__(self, name="speedmeldgain1"): super().__init__(name)

class SpeedMeldGain2(_MeldGainBase):
    MIN_GAIN = 2
    def __init__(self, name="speedmeldgain2"): super().__init__(name)

class SpeedMeldGain4(_MeldGainBase):
    MIN_GAIN = 4
    def __init__(self, name="speedmeldgain4"): super().__init__(name)

class SpeedMeldGain8(_MeldGainBase):
    MIN_GAIN = 8
    def __init__(self, name="speedmeldgain8"): super().__init__(name)

class SpeedMeldKeepWhite1(_MeldGainBase):
    MIN_GAIN = 1
    KEEP_WHITE = True
    def __init__(self, name="speedmeldkeepwhite1"): super().__init__(name)

class SpeedMeldKeepWhite2(_MeldGainBase):
    MIN_GAIN = 2
    KEEP_WHITE = True
    def __init__(self, name="speedmeldkeepwhite2"): super().__init__(name)
