# -*- coding: utf-8 -*-
"""SpeedC165 —— **快版 c156 副露**：在 speedtugc 严格门控上单向补加学习副露。"""
from __future__ import annotations

import os

from .c121meld import window_features
from .speedc121 import _MeldNet
from .speedtugc import SpeedTUGC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MELD = os.path.join(ROOT, "var", "c121_meld_net.pt")


class SpeedC165(SpeedTUGC):
    def __init__(self, name="speedc165", claim_p=0.60, meld_path=DEFAULT_MELD):
        super().__init__(name)
        self.claim_p = float(claim_p)
        self._mnet = _MeldNet(meld_path)

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        try:
            offer = view.get("offer_tile")
            if not offer:
                return False
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            feat = window_features(hand, melds, list(view.get("river") or []),
                                   view.get("all_melds") or [], offer, kind)
            p = float(self._mnet.prob([feat])[0])
        except Exception:
            return False
        return p >= self.claim_p
