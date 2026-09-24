# -*- coding: utf-8 -*-
"""C164/C165/C166：M=10 并发安全快版的机制与组合单测。"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedtug import SpeedTUG
from bot.speedc164 import SpeedC164, _pick_discard_fast_phase
from bot.speedc165 import SpeedC165
from bot.speedc166 import SpeedC166


class TestFastRoute(unittest.TestCase):
    def test_primary_key_still_shanten(self):
        self.assertIn("smin", inspect.getsource(_pick_discard_fast_phase))
        self.assertIn("if s != smin", inspect.getsource(_pick_discard_fast_phase))

    def test_no_real_ukeire_dependency(self):
        import bot.speedc164 as m
        self.assertNotIn("from .ukeire import real_ukeire", inspect.getsource(m))

    def test_phase_weights_present(self):
        self.assertEqual(tuple(SpeedC164().weights), (0.0, 1.0, 1.5))

    def test_keeps_c036(self):
        self.assertIs(SpeedC164._best_giveup, SpeedTUG._best_giveup)


class TestFastMeld(unittest.TestCase):
    def test_learnt_add_still_works(self):
        view = {"seat": 0, "phase": "response_peng", "turn": 1,
                "my_hand": ["8t", "西", "1t", "9b", "9t", "9w", "9t", "东", "5b", "西", "东", "2w", "8t"],
                "melds": [], "offer_tile": "9t", "river": ["5w", "东", "中", "2t", "1t"], "all_melds": [],
                "god": {"baotou": False, "chain_count": 0, "catch_play": False, "piao_count": 0,
                        "god_discarder_seat": -1}}
        self.assertTrue(SpeedC165()._want_claim(view, "peng", None))

    def test_keeps_c036(self):
        self.assertIs(SpeedC165._best_giveup, SpeedTUG._best_giveup)


class TestFastCombo(unittest.TestCase):
    def test_mro_and_hooks(self):
        self.assertIs(SpeedC166._pick_discard, SpeedC164._pick_discard)
        self.assertIs(SpeedC166._want_claim, SpeedC165._want_claim)

    def test_instance_has_both(self):
        p = SpeedC166()
        self.assertTrue(hasattr(p, "_mnet"))
        self.assertEqual(tuple(p.weights), (0.0, 1.0, 1.5))
        self.assertIs(SpeedC166._best_giveup, SpeedTUG._best_giveup)

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        for name in ("speedc164", "speedc165", "speedc166"):
            self.assertIn('"%s"' % name, s)


if __name__ == "__main__":
    unittest.main()
