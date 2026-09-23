# -*- coding: utf-8 -*-
"""SpeedC150 单测：**全机制束** = C146（明杠+自杠+吃碰+财飘）+ C135（真进张并列出牌）。

要点：① 四条机制钩子都在；② **c135 的弃牌钩子真的接管**（真机盘 6w→9w）；
③ `decide` 仍继承 `SpeedTUGC`（除 c135 的 `_pick_discard` 外不改决策主体）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc135 import SpeedC135          # noqa: E402
from bot.speedc141 import SpeedC141          # noqa: E402
from bot.speedc144 import SpeedC144          # noqa: E402
from bot.speedc146 import SpeedC146          # noqa: E402
from bot.speedc150 import SpeedC150          # noqa: E402
from bot.speedt import _best_discard_t       # noqa: E402
from bot.speedtugc import SpeedTUGC          # noqa: E402

C135_HAND = ["1b", "2b", "6w", "7w", "8b", "9b", "9b", "9w", "白", "西", "西"]
C135_DRAWN = "白"
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
BU_HAND = ["白", "3b", "1b", "7t", "6t", "9t", "3t", "5t", "4b", "5b", "6t"]
M_MELDS = [{"type": "peng", "tile": "1t"}]
M_HAND = ["2b", "2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白"]


def _view(phase, offer, hand, melds, drawn=None):
    return {"seat": 0, "phase": phase, "turn": 0, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": drawn,
            "offer_tile": offer, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestSpeedC150(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc150", F)
        self.assertIsInstance(F["speedc150"](), SpeedC150)

    def test_composition(self):
        self.assertIs(SpeedC150.decide, SpeedTUGC.decide)
        self.assertIs(SpeedC150._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC150._best_giveup, SpeedC141._best_giveup)
        self.assertIs(SpeedC150._pick_discard, SpeedC135._pick_discard)
        self.assertTrue(SpeedC150.SELF_GANG)

    def test_c135_discard_hook_active(self):
        """真机盘：基线 6w、c135（也就是 c150）9w。"""
        self.assertEqual(_best_discard_t(list(C135_HAND), C135_DRAWN, 1, 0), "6w")
        self.assertEqual(SpeedC150()._pick_discard(list(C135_HAND), C135_DRAWN, 1, 0), "9w")
        self.assertEqual(SpeedC150()._pick_discard(list(C135_HAND), C135_DRAWN, 1, 0),
                         SpeedC135()._pick_discard(list(C135_HAND), C135_DRAWN, 1, 0))

    def test_c146_components_still_there(self):
        # 自杠（补杠）
        v = _view("draw", None, BU_HAND, [{"type": "peng", "tile": "9t", "tiles": ["9t"] * 3}],
                  drawn=BU_HAND[-1])
        self.assertEqual((SpeedC150().decide(v) or {}).get("action"), "gang")
        # 明杠
        m = _view("response_peng", "2b", M_HAND, M_MELDS)
        self.assertEqual((SpeedC150().decide(m) or {}).get("action"), "gang")
        # 财飘（弃白）
        p = _view("draw", None, A_HAND, A_MELDS, drawn=A_DRAWN)
        act = SpeedC150().decide(p)
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))

    def test_matches_c146_on_states_without_c135_difference(self):
        """没有并列差异的局面下，c150 必须与 c146 完全一致（单变量原则）。"""
        v1 = _view("response_peng", "2b", M_HAND, M_MELDS)
        v2 = _view("response_peng", "2b", M_HAND, M_MELDS)
        self.assertEqual(SpeedC150().decide(v1), SpeedC146().decide(v2))


if __name__ == "__main__":
    unittest.main()
