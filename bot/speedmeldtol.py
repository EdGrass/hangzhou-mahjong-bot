# -*- coding: utf-8 -*-
"""Meld-tolerance gate: the unexplored half of the C136 axis.

Ladder measured on real portal replays (same rooms, top-32 peers as control;
`var/_midgame_gap.py`):

    arm                         melds/round   peer top32   >=1 meld
    speedc211  (c151 - C136)        0.83         1.27        58.7%
    speedtugc  (strict gate)        0.87         1.27        61.3%
    speedc151  (C136, MIN_GAIN=1)   1.12         1.32        71.6%
    speedtug   (allow_equal, flat)  1.25         1.20        76.2%
    ------- top-32 field -------    1.27         1.27        74.6%

C136 (R962) added the equal-shanten branch `ukeire_after >= ukeire_before + 1`
and moving 0.87 -> 1.12 was worth `c151 - tugc = +64 net/room`.  Every variant
built so far (`SpeedMeldGain1/2/4/8`) went STRICTER (MIN_GAIN >= 1).  The other
half of the axis -- accepting equal-shanten melds that cost a little ukeire --
was never tested, even though:
  * the whole c151 gain is the meld decision (R962),
  * the mid-game tenpai deficit is the dominant term of the -4.49pp win-rate gap
    (hu_gap_split: tenpai rate -6.44pp vs conversion -1.64pp),
  * and top players sit at 1.27-1.32 melds/round, ~18% above c151.

This module parameterises that direction:

    accept  <=>  after_shanten < before_shanten                       (strict)
             or (after_shanten == before_shanten
                 and after_ukeire >= before_ukeire - TOL)

    TOL=0  == C136 with MIN_GAIN=0 (accepts "flat" melds)
    TOL>0  == also accept melds that cost up to TOL live tiles, i.e. it walks
              c151 toward `speedtug`'s allow_equal behaviour, but stops short of
              it (allow_equal accepted the 23% of equal-shanten melds that make
              the hand WORSE by any amount).

Everything else (discard policy, route bonus, gang handling, P0 fix) is
inherited unchanged from SpeedC151.
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc151 import SpeedC151
from .speedtugc import want_claim_strict_meld
from .ukeire import visible_counts


class _MeldTolBase(SpeedC151):
    #: how many live tiles of ukeire we are willing to give up for a meld
    TOL = 0.0

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
            after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] < before[0]:
                return True
            if after[0] == before[0] and (after[1] or 0.0) >= (before[1] or 0.0) - self.TOL:
                return True
        return False


class SpeedMeldTol0(_MeldTolBase):
    TOL = 0.0
    def __init__(self, name="speedmeldtol0"): super().__init__(name)


class SpeedMeldTol2(_MeldTolBase):
    TOL = 2.0
    def __init__(self, name="speedmeldtol2"): super().__init__(name)


class SpeedMeldTol4(_MeldTolBase):
    TOL = 4.0
    def __init__(self, name="speedmeldtol4"): super().__init__(name)


class SpeedMeldTol8(_MeldTolBase):
    TOL = 8.0
    def __init__(self, name="speedmeldtol8"): super().__init__(name)


class SpeedMeldTol16(_MeldTolBase):
    TOL = 16.0
    def __init__(self, name="speedmeldtol16"): super().__init__(name)
