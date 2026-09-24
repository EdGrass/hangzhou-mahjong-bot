# -*- coding: utf-8 -*-
"""speedc156（c151 + 学习到的选择性副露）单测。

夹具来自真机 dec 流（`var/_find_meld_fixture2.py` 搜索）：**合法但基线拒**的碰/吃窗口，
而学习模型的置信度 ≥ 0.60 ⇒ 候选应当"补要"。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot.speedc151 as s151                              # noqa: E402
from bot.speedc151 import SpeedC151                       # noqa: E402
from bot.speedc156 import SpeedC156                       # noqa: E402

PENG = dict(hand=["8t", "西", "1t", "9b", "9t", "9w", "9t", "东", "5b", "西", "东", "2w", "8t"],
            offer="9t", river=["5w", "东", "中", "2t", "1t"], melds=[])
CHI = dict(hand=["6w", "2t", "白", "1b", "6t", "5t", "2w", "7w", "白", "5w", "3w", "1w", "2b"],
           offer="4w", river=["中", "北", "西", "南", "发", "9t", "4w"], melds=[])


def _view(spec, phase):
    return {"seat": 0, "phase": phase, "turn": 1, "my_hand": list(spec["hand"]),
            "melds": list(spec["melds"]), "offer_tile": spec["offer"],
            "river": list(spec["river"]), "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC156LearnedMeldAdd(unittest.TestCase):
    def test_fixture_is_discriminating(self):
        self.assertFalse(SpeedC151()._want_claim(_view(PENG, "response_peng"), "peng", None),
                         "夹具前提：基线（质量门控）必须拒绝这个碰")
        self.assertFalse(SpeedC151()._want_claim(_view(CHI, "response_chi"), "chi", None),
                         "夹具前提：基线必须拒绝这个吃")

    def test_adds_when_model_confident(self):
        pol = SpeedC156()
        self.assertTrue(pol._want_claim(_view(PENG, "response_peng"), "peng", None))
        self.assertTrue(pol._want_claim(_view(CHI, "response_chi"), "chi", None))

    def test_never_vetoes_base_claim(self):
        pol = SpeedC156()
        orig = s151.SpeedC151._want_claim
        try:
            s151.SpeedC151._want_claim = lambda self, v, k, p=None: True
            self.assertTrue(pol._want_claim(_view(PENG, "response_peng"), "peng", None),
                            "本臂只允许单向增加（不否决任何基线索取）")
        finally:
            s151.SpeedC151._want_claim = orig

    def test_missing_offer_returns_false(self):
        pol = SpeedC156()
        v = _view(PENG, "response_peng")
        v["offer_tile"] = None
        self.assertFalse(pol._want_claim(v, "peng", None))

    def test_does_not_touch_discard_layer(self):
        self.assertIs(SpeedC156._pick_discard, SpeedC151._pick_discard)

    def test_source_guardrails(self):
        src = inspect.getsource(SpeedC156)
        self.assertIn("super()._want_claim(", src)
        self.assertIn("window_features(", src)
        self.assertIn("claim_p", src)
