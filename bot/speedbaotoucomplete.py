# -*- coding: utf-8 -*-
# Narrow baotou rule: accept a claim ONLY when it completes the "4 groups + 白"
# baotou shape (any draw then wins, and it is a x2 multiplier).
#
# Why this shape and not a general loosening: R1013 showed baotou comes from the
# MELDED route, but R977 showed that relaxing the claim gate in general is
# clearly harmful (it admits melds with negative ukeire change).  R1014 showed
# that a baotou term inside the DISCARD score is structurally inert (0.3-0.4%
# footprint even at 5x weight), because discarding a tile rarely changes the
# number of completed groups.  So the only place a baotou-seeking rule can act is
# the claim decision, and this variant restricts it to the exact completing case.
from __future__ import annotations

from mahjong.hu import is_baotou

from .speedc151 import SpeedC151
from .speedvalue import SpeedValue


class _BaotouCompleteMixin:
    def _completes_baotou(self, view, kind, pair):
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        offer = view.get("offer_tile")
        if not offer or "白" not in hand:
            return False
        h2 = list(hand)
        try:
            if kind == "peng":
                for _ in range(2):
                    h2.remove(offer)
                e2, g2 = e + 1, g
            elif kind == "gang_ming":
                for _ in range(3):
                    h2.remove(offer)
                e2, g2 = e + 1, g + 1
            else:
                for x in (pair or []):
                    h2.remove(x)
                e2, g2 = e + 1, g
        except Exception:
            return False
        for d in sorted(set(h2)):
            rem = list(h2)
            rem.remove(d)
            if len(rem) != 13 - 3 * e2 - g2:
                continue
            try:
                if is_baotou(rem, allow_qidui=(e2 == 0 and g2 == 0),
                             exposed_melds=e2, gangs=g2):
                    return True
            except Exception:
                continue
        return False

    def _want_claim(self, view, kind, pair=None):
        if kind in ("chi", "peng", "gang_ming") and self._completes_baotou(view, kind, pair):
            return True
        return super()._want_claim(view, kind, pair)


class SpeedBaotouComplete(_BaotouCompleteMixin, SpeedValue):
    """On top of the value policy."""

    def __init__(self, name="speedbaotoucomplete"):
        super().__init__(name)


class SpeedBaotouCompleteC151(_BaotouCompleteMixin, SpeedC151):
    """Isolated: c151 + the narrow baotou-completing claim rule."""

    def __init__(self, name="speedbaotoucompletec151"):
        super().__init__(name)
