# -*- coding: utf-8 -*-
"""YouCaiBiKao=true INSURANCE twins of the main candidates (see tools/rules_guard.py).

Rule risk (guide §1.6 + rules_guard doc): the tournament config may set
`YouCaiBiKao=true` = "holding 白 forbids 平胡; you may only win by 爆头 or 杠开/链".
If we run a normal arm under that rule, our 白-平胡 wins (64.4% of our wins) get
409-rejected; and the discard route should change too (keep 白 as the pair-wait).

`FastYCBKMixin` (bot/ycbk_fast.py) provides both halves:
  * GOD_MELD=False            -> 白 no longer completes melds, so the chooser aims at
                                 "4 melds + lone 白" = 爆头 (and the chain/杠 routes),
  * YOU_CAI_BI_KAO=True + decide() wrapper -> refuse to declare an illegal 平胡 win
                                 and instead keep playing (discard via the same hook).

These twins are the insurance arms: switch to them ONLY after
`python -X utf8 tools/rules_guard.py --strategy <arm> --token-file <NEW> ` says the
tournament needs the gate (it returns 2 when inconsistent).
"""
from __future__ import annotations

from .speedchirealized import SpeedMeldMore0Chi
from .speedmeldtoldose import SpeedMeldTol2Chi
from .speedgangtakefixed import SpeedGangTakeFixed
from .speedvalue import SpeedValue
from .ycbk_fast import FastYCBKMixin


class SpeedValueYCBK(FastYCBKMixin, SpeedValue):
    """YouCaiBiKao=true twin of `speedvalue` (campaign-2 candidate)."""

    def __init__(self, name="speedvalueycbk"):
        super().__init__(name)


class SpeedGangTakeFixedYCBK(FastYCBKMixin, SpeedGangTakeFixed):
    """YouCaiBiKao=true twin of `speedgangtakefixed` (campaign-3 candidate)."""

    def __init__(self, name="speedgangtakefixedycbk"):
        super().__init__(name)


class SpeedMeldMore0ChiYCBK(FastYCBKMixin, SpeedMeldMore0Chi):
    """YouCaiBiKao=true twin of the meld bundle (campaign-4 candidate)."""

    def __init__(self, name="speedmeldmore0chiycbk"):
        super().__init__(name)

class SpeedMeldTol2ChiYCBK(FastYCBKMixin, SpeedMeldTol2Chi):
    """YouCaiBiKao=true twin of the (current) 役 4 candidate `SpeedMeldTol2Chi`."""

    def __init__(self, name="speedmeldtol2chiycbk"):
        super().__init__(name)

