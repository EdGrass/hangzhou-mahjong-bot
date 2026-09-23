# -*- coding: utf-8 -*-
"""c177~c179：fast c136 记录臂的导入/钩子/被否边界回归。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc141 import SpeedC141
from bot.speedc144 import SpeedC144
from bot.speedc177 import SpeedC177
from bot.speedc178 import SpeedC178
from bot.speedc179 import SpeedC179
from bot.speedtugc import SpeedTUGC

FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])


def _view(x):
    ph, o, h, m = x
    return {"seat": 0, "phase": ph, "turn": 1, "responding_seats": [0],
            "my_hand": list(h), "melds": list(m), "drawn_tile": None,
            "offer_tile": o, "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "god_discarder_seat": -1}}


class TestFastC136Record(unittest.TestCase):
    def test_hooks(self):
        self.assertIs(SpeedC178._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC178._best_giveup, SpeedC141._best_giveup)
        self.assertIs(SpeedC179._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC179._best_giveup, SpeedC141._best_giveup)
        self.assertTrue(SpeedC178().SELF_GANG)
        self.assertTrue(SpeedC179().SELF_GANG)
        self.assertTrue(SpeedC179().YOU_CAI_BI_KAO)

    def test_fast_proxy_is_known_too_conservative(self):
        """记录被否事实：full c136 会收 FIX1，fast c177 不收。"""
        self.assertEqual((SpeedC177().decide(_view(FIX1)) or {}).get("action"), "pass")

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            s = fh.read()
        for name in ("speedc177", "speedc178", "speedc179"):
            self.assertIn('"%s"' % name, s)


if __name__ == "__main__":
    unittest.main()
