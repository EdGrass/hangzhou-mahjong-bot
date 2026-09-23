# -*- coding: utf-8 -*-
"""Dose ladder for the 碰 axis, with the pair-exact 吃 gate (supersedes TOL guesses).

Measured gap (authoritative, 728 games): our 碰 decision rate 75.8% of client-seen
windows vs the leaderboard-top cohort's implied ~92% (realised 71.0% / offering
77.1%).  `SpeedMeldMore0Chi` (equal shanten AND no ukeire loss) only adds ~1.4pp on
the 碰 side -- so the axis needs an explicit DOSE ladder:

    TOL=0  equal shanten, ukeire must not drop        -> SpeedMeldMore0Chi (ready)
    TOL=2  equal shanten, may cost <= 2 live tiles    -> this file
    TOL=4  equal shanten, may cost <= 4 live tiles    -> this file

All three keep the pair-exact 吃 branch (ChiRealizedMixin) and never accept a 碰 that
worsens the shanten.
"""
from __future__ import annotations

from .speedchirealized import ChiRealizedMixin
from .speedmeldtol import SpeedMeldTol2, SpeedMeldTol4


class SpeedMeldTol2Chi(ChiRealizedMixin, SpeedMeldTol2):
    """Equal-shanten 碰 with up to 2 live tiles of ukeire loss; 吃 stays pair-exact."""

    def __init__(self, name="speedmeldtol2chi"):
        super().__init__(name)


class SpeedMeldTol4Chi(ChiRealizedMixin, SpeedMeldTol4):
    """Equal-shanten 碰 with up to 4 live tiles of ukeire loss; 吃 stays pair-exact."""

    def __init__(self, name="speedmeldtol4chi"):
        super().__init__(name)
