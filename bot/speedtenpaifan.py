# -*- coding: utf-8 -*-
"""Fan-first tenpai tie-break -- derived from a FITTED exchange rate, not a guess.

M1/M2 (`var/_value_dataset.py` + `var/_value_fit.py`, 59,155 candidate rows from
real portal replays, split by room) fitted  score ~ state  inside each shanten
bucket:

    sh=1:  1 extra live ukeire tile  = +0.080 points/round
    sh=0:  1 extra live wait tile    = +0.118 points/round
    sh=0:  1 extra fan               = +3.75 points/round
    sh=0:  holding 白                = +5.55 points/round

i.e. **one fan is worth ~32-47 live tiles**.  The strong players behave exactly
that way: they take deliberately narrower tenpai waits (0.60% of discards vs our
0.02%, `var/_discard_regret_cohort.py`) and end up with 番/胡 1.39 vs our 1.31.

But `speedc151`'s key at tenpai is
    key = (s, -len(waits(...)), -u, _pref, drawn)      with u == 0 at s == 0
so it maximises the NUMBER OF WAIT TILE TYPES and **never looks at fan at all**.
The two existing variants (`SpeedTenpaiLive`, `SpeedTenpaiLiveFan`) only ever
move to a *wider* wait -- the fan-for-width direction was never implemented.

This arm implements it directly and conservatively:

    at tenpai, override c151's discard ONLY IF some other tenpai discard has
    STRICTLY higher max achievable fan; ties keep c151's tuned tie-break.

`SpeedTenpaiMaxFanTol4` adds a width floor (allow giving up at most 4 live wait
tiles) so the trade is bounded rather than extrapolating the fit.
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

from .speedc151 import SpeedC151, _pref
from .speedc135 import _pref as _pref135
from .speedtenpai import _TenpaiBase
from .ukeire import visible_counts


class _FanFirstBase(_TenpaiBase):
    """Override only for STRICTLY more fan; optional bound on the width given up."""

    MAX_WIDTH_LOSS = None          # None = unbounded

    def __init__(self, name="speedtenpaimaxfan"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = SpeedC151._pick_discard(self, hand, drawn, exposed, gangs, view=view)
        if base not in hand or not view:
            return base
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            return base
        try:
            rem0 = list(hand)
            rem0.remove(base)
            s0 = exact_shanten(rem0, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs,
                               god_meld=self.GOD_MELD)
        except Exception:
            return base
        if s0 != 0:
            return base
        f0 = self._max_fan(rem0, exposed, gangs, view)
        l0 = self._live_wait_count(rem0, exposed, gangs, vis)
        if f0 is None or l0 is None:
            return base
        best_t, best = None, (f0, l0)
        for d in sorted(set(hand)):
            if d == base:
                continue
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs,
                                  god_meld=self.GOD_MELD)
            except Exception:
                continue
            if s != 0:
                continue
            f = self._max_fan(rem, exposed, gangs, view)
            lv = self._live_wait_count(rem, exposed, gangs, vis)
            if f is None or lv is None or f <= f0:
                continue                      # fan must STRICTLY improve
            if self.MAX_WIDTH_LOSS is not None and lv < l0 - self.MAX_WIDTH_LOSS:
                continue                      # width floor
            key = (f, lv, -_pref135(d, hand))
            if best_t is None or key > (best[0], best[1], -_pref135(best_t, hand)):
                best_t, best = d, (f, lv)
        return best_t if best_t is not None else base


class SpeedTenpaiMaxFan(_FanFirstBase):
    """Unbounded fan-for-width trade."""

    MAX_WIDTH_LOSS = None

    def __init__(self, name="speedtenpaimaxfan"):
        super().__init__(name)


class SpeedTenpaiMaxFanTol4(_FanFirstBase):
    """Fan first, but never give up more than 4 live wait tiles."""

    MAX_WIDTH_LOSS = 4

    def __init__(self, name="speedtenpaimaxfantol4"):
        super().__init__(name)


class SpeedTenpaiMaxFanTol8(_FanFirstBase):
    """Fan first, but never give up more than 8 live wait tiles."""

    MAX_WIDTH_LOSS = 8

    def __init__(self, name="speedtenpaimaxfantol8"):
        super().__init__(name)
