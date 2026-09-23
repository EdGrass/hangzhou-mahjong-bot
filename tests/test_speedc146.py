# -*- coding: utf-8 -*-
"""SpeedC146 单测：**全缺陷组合臂（最大束）** = C144 明杠 + C134 自杠 + C136 吃碰 + C141 财飘。

四个成分各自用真机/既有 fixture 钉住；另验证 MRO 链（C144 → C136）与 `SELF_GANG=True`。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc136 import SpeedC136          # noqa: E402
from bot.speedc141 import SpeedC141          # noqa: E402
from bot.speedc144 import SpeedC144          # noqa: E402
from bot.speedc146 import SpeedC146          # noqa: E402
from bot.speedtugc import SpeedTUGC          # noqa: E402

# —— C141 财飘盘
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
# —— C136 两个真机副露窗口
FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
FIX2 = ("response_chi", "1b",
        ["8t", "2b", "5w", "1b", "8w", "8t", "2t", "3b", "5w", "6t", "2b", "2b", "1w"], [])
# —— C144 明杠盘
M_MELDS = [{"type": "peng", "tile": "1t"}]
M_HAND = ["2b", "2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白"]
# —— C134 自杠盘（补杠：碰 9t + 手上第 4 张）
BU_HAND = ["白", "3b", "1b", "7t", "6t", "9t", "3t", "5t", "4b", "5b", "6t"]
QIDUI_HAND = ["1w", "1w", "1w", "1w", "2w", "2w", "3w", "3w",
              "4b", "4b", "5b", "5b", "6t", "7b"]


def _peng(t):
    return {"type": "peng", "tile": t, "tiles": [t] * 3}


def _view(phase, offer, hand, melds, cp=False, river_len=6):
    return {"seat": 0, "phase": phase, "turn": 0, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "river_len": river_len,
            "all_melds": [], "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": cp,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestSpeedC146(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc146", F)
        self.assertIsInstance(F["speedc146"](), SpeedC146)

    def test_composition(self):
        self.assertIs(SpeedC146.decide, SpeedTUGC.decide)
        self.assertIs(SpeedC146._want_claim, SpeedC144._want_claim)
        self.assertIs(SpeedC146._best_giveup, SpeedC141._best_giveup)
        self.assertIs(SpeedC146._pick_discard, SpeedTUGC._pick_discard)
        self.assertIs(SpeedC146._maybe_gang, SpeedTUGC._maybe_gang)
        self.assertTrue(SpeedC146.SELF_GANG)
        self.assertFalse(SpeedTUGC.SELF_GANG)

    def test_c134_self_gang_wired(self):
        """补杠：碰 9t + 手上第 4 张 ⇒ 杠（基线不杠）。"""
        v = _view("draw", None, BU_HAND, [_peng("9t")])
        v["drawn_tile"] = BU_HAND[-1]
        self.assertEqual((SpeedTUGC().decide(v) or {}).get("action"), "discard")
        act = SpeedC146().decide(v)
        self.assertEqual((act or {}).get("action"), "gang")
        self.assertEqual(act.get("tile"), "9t")

    def test_c134_keeps_qidui_route(self):
        v = _view("draw", None, QIDUI_HAND, [])
        v["drawn_tile"] = QIDUI_HAND[-1]
        self.assertEqual((SpeedC146().decide(v) or {}).get("action"), "discard")

    def test_c144_ming_gang(self):
        v = _view("response_peng", "2b", M_HAND, M_MELDS)
        self.assertEqual((SpeedC146().decide(v) or {}).get("action"), "gang")
        self.assertEqual(SpeedC146().decide(v), SpeedC144().decide(v))

    def test_c136_reached_through_mro(self):
        for fix in (FIX1, FIX2):
            self.assertEqual(SpeedC146().decide(_view(*fix)), SpeedC136().decide(_view(*fix)))
        self.assertEqual((SpeedC146().decide(_view(*FIX1)) or {}).get("action"), "peng")
        self.assertEqual((SpeedC146().decide(_view(*FIX2)) or {}).get("action"), "pass")

    def test_c141_piao(self):
        ch = {"count": 0, "piao": 0}
        self.assertEqual(SpeedC146()._best_giveup(list(A_HAND), 2, 0, 2, ch), "白")
        v = _view("draw", None, A_HAND, A_MELDS)
        v["drawn_tile"] = A_DRAWN
        act = SpeedC146().decide(v)
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))
        v2 = _view("draw", None, A_HAND, A_MELDS)
        v2["drawn_tile"] = A_DRAWN
        self.assertEqual(SpeedTUGC().decide(v2).get("action"), "hu")


if __name__ == "__main__":
    unittest.main()
