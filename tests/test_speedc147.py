# -*- coding: utf-8 -*-
"""SpeedC147 单测：**条件组合臂** = C073w4（BC 弃牌模型）+ C146 的四个机制钩子。

关键回归：`C067Policy.decide()` 覆盖整条弃牌路径、不查 `_maybe_gang`，
组合时必须把「可胡」「可自杠」两段补回来，否则会**静默旁路 C134 的暗杠/补杠**。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc067 import C067Policy          # noqa: E402
from bot.speedc141 import SpeedC141           # noqa: E402
from bot.speedc144 import SpeedC144           # noqa: E402
from bot.speedc146 import SpeedC146           # noqa: E402
from bot.speedc147 import SpeedC147           # noqa: E402
from bot.speedtugc import SpeedTUGC           # noqa: E402

# —— BC 模型真机盘：c146 弃 2b，c147（模型）弃 9w
BC_HAND = ["2b", "3t", "4w", "6b", "6t", "6w", "7t", "8b", "8w", "8w", "9t", "9t", "9w", "白"]
BC_DRAWN = "6b"
# —— C141 财飘盘
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
# —— C134 补杠盘（碰 9t + 手上第 4 张）
BU_HAND = ["白", "3b", "1b", "7t", "6t", "9t", "3t", "5t", "4b", "5b", "6t"]
# —— C144 明杠盘
M_MELDS = [{"type": "peng", "tile": "1t"}]
M_HAND = ["2b", "2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白"]


def _view(phase, offer, hand, melds, drawn=None, river_len=6):
    return {"seat": 0, "phase": phase, "turn": 0, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": drawn,
            "offer_tile": offer, "river": [], "river_len": river_len,
            "all_melds": [], "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestSpeedC147(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc147", F)
        self.assertIsInstance(F["speedc147"](), SpeedC147)

    def test_composition(self):
        self.assertIs(SpeedC147._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC147._best_giveup, SpeedC141._best_giveup)
        self.assertTrue(SpeedC147.SELF_GANG)
        self.assertIsInstance(SpeedC147(), C067Policy)
        self.assertIsInstance(SpeedC147(), SpeedC146)

    def test_self_gang_not_bypassed(self):
        """回归：C067Policy 的弃牌路径不得旁路 _maybe_gang（补杠应照做）。"""
        v = _view("draw", None, BU_HAND, [{"type": "peng", "tile": "9t", "tiles": ["9t"] * 3}],
                  drawn=BU_HAND[-1])
        self.assertEqual((SpeedTUGC().decide(v) or {}).get("action"), "discard")
        act = SpeedC147().decide(v)
        self.assertEqual((act or {}).get("action"), "gang")
        self.assertEqual(act.get("tile"), "9t")

    def test_ming_gang_and_piao_still_work(self):
        m = _view("response_peng", "2b", M_HAND, M_MELDS)
        self.assertEqual((SpeedC147().decide(m) or {}).get("action"), "gang")
        p = _view("draw", None, A_HAND, A_MELDS, drawn=A_DRAWN)
        act = SpeedC147().decide(p)
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))

    def test_bc_model_is_active(self):
        """模型真的接管弃牌：同一盘 c146 弃 2b、c147 弃 9w。"""
        v1 = _view("draw", None, BC_HAND, [], drawn=BC_DRAWN)
        v2 = _view("draw", None, BC_HAND, [], drawn=BC_DRAWN)
        self.assertEqual((SpeedC146().decide(v1) or {}).get("tile"), "2b")
        self.assertEqual((SpeedC147().decide(v2) or {}).get("tile"), "9w")

    def test_missing_model_falls_back(self):
        """模型缺失时不得抛异常（回退到 c146 行为）。"""
        s = SpeedC147(model_path="var/__no_such_model__.pt")
        v = _view("draw", None, BC_HAND, [], drawn=BC_DRAWN)
        act = s.decide(v)
        self.assertEqual((act or {}).get("action"), "discard")


if __name__ == "__main__":
    unittest.main()
