# -*- coding: utf-8 -*-
"""§Q tail candidate: 碰 with a bounded +1-shanten tolerance (guarded).

Evidence (R1054, authoritative): the leaderboard-top cohort faces the SAME legal 碰
windows as we do (0.824 vs 0.812 per round) but accepts 73.2% of them vs our 57.5%.
Our equal-shanten ladder (`speedmeldtoldose`, up to 4 live tiles of ukeire loss) caps
at 81.7% decision rate ~= 62% realised, so the remaining ~11pp can only come from
accepting a 碰 that RAISES the shanten by 1.

Guards (all must hold, fail-closed):
  1. current exposed melds <= 2      (do not over-meld a hand that is already open)
  2. s_before >= 2                   (never in tenpai / 1-shanten)
  3. live copies of the pair tile >= 2 (not a dead pair)
  4. wall guard: river_len <= SELF_GANG_MAX_RIVER - 10  (keep the endgame intact)
  5. never accept s_after >= s_before + 2

Counter-evidence kept in mind: in our own real-machine history the meld-heavier
`speedtugc` (1.25 melds/round) was WORSE than c151 (1.12) by +53.8 net/room, so
"more melds" is not automatically good -- this arm is a probe, not a presumed win.
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedchirealized import SpeedMeldMore0Chi
from .speedc136 import _after_best, _state
from .ukeire import visible_counts


class SpeedMeldPengWiden(SpeedMeldMore0Chi):
    MAX_MELDS = 2
    MIN_SHANTEN = 2
    MIN_LIVE_PAIR = 2

    def __init__(self, name="speedmeldpengwiden"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True                      # superset: never take away an accept
        if kind != "peng":
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return False
        if e > self.MAX_MELDS:
            return False
        try:
            river_len = len(view.get("river") or [])
        except Exception:
            river_len = 0
        limit = int(getattr(self, "SELF_GANG_MAX_RIVER", 56)) - 10
        if river_len > limit:
            return False
        vis = visible_counts(hand, river=view.get("river"),
                             all_melds=view.get("all_melds"))
        before = _state(hand, e, g, vis, self.GOD_MELD)
        if before is None or before[0] is None or before[0] < self.MIN_SHANTEN:
            return False
        live_pair = 4 - int(vis.get(offer, 0))
        if live_pair < self.MIN_LIVE_PAIR:
            return False
        after = _after_best(hand, offer, "peng", None, e, g, vis, self.GOD_MELD)
        if after is None or after[0] is None:
            return False
        return after[0] == before[0] + 1      # bounded: exactly +1 shanten
