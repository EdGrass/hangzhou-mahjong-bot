# -*- coding: utf-8 -*-
"""C190：学习副露层叠在已验证 speedtugc 上，并保留无白坏窗口否决。"""
import io, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from bot.speedtugc import SpeedTUGC
from bot.speedc190 import SpeedC190


def _view(phase, offer, hand, melds, god=None):
    return {"seat": 1, "phase": phase, "turn": 0, "responding_seats": [1],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [],
            "god": god or {"baotou": False, "chain_count": 0, "catch_play": False,
                           "piao_count": 0, "god_discarder_seat": -1}}

# c136 真机 fixture：严格门控 pass、质量进张变好；学习层应补成 peng。
QUALITY_UP = _view("response_peng", "5t",
    ["白","5t","6b","9t","6w","8t","3t","7t","5t","6t","2t","8w","8t"], [])
# c188 真机 fixture：无白且学习层额外想 chi，但真实进张 90→87，应否决。
BAD_NO_WHITE = _view("response_chi", "1b",
    ["西","1b","8t","1w","2b","3b","7b","4b","9w","2t"],
    [{"type":"peng","tile":"发","tiles":["发","发","发"]}])
# 含白路线：即使真实进张口径不稳，也应保留学习层选择。
WHITE_ROUTE = _view("response_chi", "7w",
    ["1w","2t","白","1w","3t","8w","6t","6w","5t","7w"],
    [{"type":"peng","tile":"9w","tiles":["9w","9w","9w"]}])


class TestSpeedC190(unittest.TestCase):
    def test_registered_and_subclasses_baseline(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc190", F)
        self.assertIsInstance(F["speedc190"](), SpeedC190)
        self.assertAlmostEqual(F["speedc190"]().claim_p, 0.75)
        self.assertTrue(issubclass(SpeedC190, SpeedTUGC))

    def test_learned_layer_adds_quality_window(self):
        self.assertEqual((SpeedTUGC().decide(QUALITY_UP) or {}).get("action"), "pass")
        self.assertEqual((SpeedC190(claim_p=0.60).decide(QUALITY_UP) or {}).get("action"), "peng")

    def test_vetoes_no_white_down_window(self):
        self.assertEqual((SpeedC190(claim_p=0.60).decide(BAD_NO_WHITE) or {}).get("action"), "pass")

    def test_preserves_white_route(self):
        self.assertEqual((SpeedC190(claim_p=0.60).decide(WHITE_ROUTE) or {}).get("action"), "chi")

    def test_source_guardrails(self):
        with io.open(os.path.join(ROOT,"bot","speedc190.py"),encoding="utf-8") as fh: s=fh.read()
        self.assertIn('if "白" in hand:', s)
        self.assertIn("DEFAULT_MELD", s)


if __name__ == "__main__": unittest.main()
