# -*- coding: utf-8 -*-
"""C188 安全版 c186 的回归：保留含白/正向窗口，只否决无白且真实进张变差的额外副露。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import SpeedC151
from bot.speedc186 import SpeedC186
from bot.speedc188 import SpeedC188


def _view(phase, offer, hand, melds, god=None):
    return {"seat": 1, "phase": phase, "turn": 0, "responding_seats": [1],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [],
            "god": god or {"baotou": False, "chain_count": 0, "catch_play": False,
                           "piao_count": 0, "god_discarder_seat": -1}}


# 真机 fixture：c151 pass / c186 chi，且手牌无白、真实进张 90→87。
BAD_NO_WHITE = _view(
    "response_chi", "1b",
    ["西", "1b", "8t", "1w", "2b", "3b", "7b", "4b", "9w", "2t"],
    [{"type": "peng", "tile": "发", "tiles": ["发", "发", "发"]}],
)

# 真机 fixture：c151 pass / c186 chi，但手牌含白；C188 应保留模型选择。
WHITE_ROUTE = _view(
    "response_chi", "7w",
    ["1w", "2t", "白", "1w", "3t", "8w", "6t", "6w", "5t", "7w"],
    [{"type": "peng", "tile": "9w", "tiles": ["9w", "9w", "9w"]}],
)

# c136/c146 fixture：base 质量门控本就接受的碰。
BASE_ACCEPT = _view(
    "response_peng", "5t",
    ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"],
    [],
)


class TestSpeedC188(unittest.TestCase):
    def test_registered_and_subclasses_c186(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc188", F)
        self.assertIsInstance(F["speedc188"](), SpeedC188)
        self.assertTrue(issubclass(SpeedC188, SpeedC186))

    def test_vetoes_no_white_down_window(self):
        self.assertEqual((SpeedC151().decide(BAD_NO_WHITE) or {}).get("action"), "pass")
        self.assertEqual((SpeedC186().decide(BAD_NO_WHITE) or {}).get("action"), "chi")
        self.assertEqual((SpeedC188().decide(BAD_NO_WHITE) or {}).get("action"), "pass")

    def test_preserves_white_route(self):
        self.assertEqual((SpeedC186().decide(WHITE_ROUTE) or {}).get("action"), "chi")
        self.assertEqual((SpeedC188().decide(WHITE_ROUTE) or {}).get("action"), "chi")

    def test_base_accept_is_untouched(self):
        self.assertEqual((SpeedC151().decide(BASE_ACCEPT) or {}).get("action"), "peng")
        self.assertEqual((SpeedC188().decide(BASE_ACCEPT) or {}).get("action"), "peng")

    def test_source_guardrail(self):
        import io
        with io.open(os.path.join(ROOT, "bot", "speedc188.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('if "白" in hand:', s)
        self.assertIn("return True", s)


if __name__ == "__main__":
    unittest.main()
