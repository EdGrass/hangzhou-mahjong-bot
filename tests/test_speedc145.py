# -*- coding: utf-8 -*-
"""SpeedC145 单测：同房缺陷组合臂 = C144(明杠) + C136(吃碰质量) + C141(财飘)。

每个成分都用真机盘钉住；另外验证 MRO 让 C144 的 `_want_claim` 能正确链到 C136 的 `super()`。
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
from bot.speedc145 import SpeedC145          # noqa: E402
from bot.speedtugc import SpeedTUGC          # noqa: E402

# C141 财飘盘
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
# C136 两个真机副露窗口
FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
FIX2 = ("response_chi", "1b",
        ["8t", "2b", "5w", "1b", "8w", "8t", "2t", "3b", "5w", "6t", "2b", "2b", "1w"], [])
# C144 明杠盘（已有副露 + 手上 3 张）
M_MELDS = [{"type": "peng", "tile": "1t"}]
M_HAND = ["2b", "2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白"]


def _view(phase, offer, hand, melds, cp=False):
    return {"seat": 0, "phase": phase, "turn": 1, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [], "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": cp,
                    "piao_count": 0, "god_discarder_seat": -1}}


def _draw_view(hand, drawn, melds):
    v = _view("draw", None, hand, melds)
    v["turn"] = 0
    v["drawn_tile"] = drawn
    return v


class TestSpeedC145(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc145", F)
        self.assertIsInstance(F["speedc145"](), SpeedC145)

    def test_composition(self):
        self.assertIs(SpeedC145.decide, SpeedTUGC.decide)               # 决策主体未改
        self.assertIs(SpeedC145._want_claim, SpeedC144._want_claim)     # 明杠先判
        self.assertIs(SpeedC145._best_giveup, SpeedC141._best_giveup)   # 财飘
        self.assertIs(SpeedC145._pick_discard, SpeedTUGC._pick_discard)  # 不含 C135
        self.assertIs(SpeedC145._maybe_gang, SpeedTUGC._maybe_gang)      # 不含 C134

    def test_c144_component(self):
        v = _view("response_peng", "2b", M_HAND, M_MELDS)
        self.assertEqual((SpeedC145().decide(v) or {}).get("action"), "gang")
        self.assertEqual(SpeedC145().decide(v), SpeedC144().decide(v))

    def test_c136_component_reached_through_mro(self):
        """C144 的 _want_claim 里 super() 必须链到 C136（否则组合臂会静默丢掉 C136）。"""
        for fix in (FIX1, FIX2):
            a = SpeedC145().decide(_view(*fix))
            b = SpeedC136().decide(_view(*fix))
            self.assertEqual(a, b)
        self.assertEqual((SpeedC145().decide(_view(*FIX1)) or {}).get("action"), "peng")
        self.assertEqual((SpeedC145().decide(_view(*FIX2)) or {}).get("action"), "pass")

    def test_c141_component(self):
        ch = {"count": 0, "piao": 0}
        self.assertEqual(SpeedC145()._best_giveup(list(A_HAND), 2, 0, 2, ch), "白")
        act = SpeedC145().decide(_draw_view(A_HAND, A_DRAWN, A_MELDS))
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))
        self.assertEqual(SpeedTUGC().decide(_draw_view(A_HAND, A_DRAWN, A_MELDS)).get("action"), "hu")

    def test_discard_path_is_baseline(self):
        """不含 C135 ⇒ 出牌路径必须与基线一致（延迟安全）。"""
        hand = ["1b", "2b", "6w", "7w", "8b", "9b", "9b", "9w", "白", "西", "西"]
        self.assertEqual(SpeedC145()._pick_discard(list(hand), "白", 1, 0),
                         SpeedTUGC()._pick_discard(list(hand), "白", 1, 0))


if __name__ == "__main__":
    unittest.main()
