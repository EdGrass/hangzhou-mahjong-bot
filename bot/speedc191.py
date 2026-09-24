# -*- coding: utf-8 -*-
"""SpeedC191 —— c190 的进取阈值档（claim_p=0.70）。"""
from __future__ import annotations

from .speedc190 import SpeedC190

CLAIM_P = 0.70


class SpeedC191(SpeedC190):

    def __init__(self, name="speedc191", claim_p=CLAIM_P):
        super().__init__(name, claim_p=claim_p)
