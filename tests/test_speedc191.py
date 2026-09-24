# -*- coding: utf-8 -*-
"""C191：c190 的进取阈值档回归。"""
import os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from bot.speedc190 import SpeedC190
from bot.speedc191 import SpeedC191
class TestC191(unittest.TestCase):
    def test_registered_subclass_threshold(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc191",F); p=F["speedc191"]()
        self.assertIsInstance(p,SpeedC191); self.assertTrue(issubclass(SpeedC191,SpeedC190)); self.assertAlmostEqual(p.claim_p,0.70)
if __name__=="__main__": unittest.main()
