# -*- coding: utf-8 -*-
"""SpeedC142 单测：**组合臂** = speedtugc + C136(质量副露) + C135(真进张出牌) + C141(财飘弃胡)。

每个成分都用**真机盘**钉住（fixture 来源见各自单测文件），确保组合臂没有把任一机制丢掉，
且除三处钩子外与 `SpeedTUGC` 完全一致。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc135 import SpeedC135                # noqa: E402
from bot.speedc136 import SpeedC136                # noqa: E402
from bot.speedc141 import SpeedC141                # noqa: E402
from bot.speedc142 import SpeedC142                # noqa: E402
from bot.speedtug import SpeedTUG                  # noqa: E402
from bot.speedtugc import SpeedTUGC                # noqa: E402

# —— C141 财飘盘（4 面子 + 2 白，已爆头 fan_now=2）
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]
# —— C136 两个真机副露窗口
FIX1 = ("response_peng", "5t",
        ["白", "5t", "6b", "9t", "6w", "8t", "3t", "7t", "5t", "6t", "2t", "8w", "8t"], [])
FIX2 = ("response_chi", "1b",
        ["8t", "2b", "5w", "1b", "8w", "8t", "2t", "3b", "5w", "6t", "2b", "2b", "1w"], [])
# —— C135 真机弃牌盘
F_HAND = ["1b", "2b", "6w", "7w", "8b", "9b", "9b", "9w", "白", "西", "西"]


def _view(phase, offer, hand, melds):
    return {"seat": 0, "phase": phase, "turn": 1, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


def _draw_view(hand, drawn, melds):
    v = _view("draw", None, hand, melds)
    v["turn"] = 0
    v["drawn_tile"] = drawn
    return v


class TestSpeedC142(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc142", F)
        self.assertIsInstance(F["speedc142"](), SpeedC142)

    def test_decide_inherited_and_three_hooks_only(self):
        self.assertIs(SpeedC142.decide, SpeedTUGC.decide)
        self.assertIsNot(SpeedC142._want_claim, SpeedTUGC._want_claim)
        self.assertIsNot(SpeedC142._pick_discard, SpeedTUGC._pick_discard)
        self.assertIsNot(SpeedC142._best_giveup, SpeedTUGC._best_giveup)
        self.assertIs(SpeedC142._maybe_gang, SpeedTUGC._maybe_gang)

    def test_c136_component_wired(self):
        self.assertEqual(SpeedC142().decide(_view(*FIX1)).get("action"), "peng")
        self.assertEqual(SpeedC142().decide(_view(*FIX2)).get("action"), "pass")
        # 与 C136 单变量逐位一致
        for fix in (FIX1, FIX2):
            self.assertEqual(SpeedC142().decide(_view(*fix)),
                             SpeedC136().decide(_view(*fix)))

    def test_c135_component_wired(self):
        self.assertEqual(SpeedC142()._pick_discard(list(F_HAND), "白", 1, 0), "9w")
        self.assertEqual(SpeedC142()._pick_discard(list(F_HAND), "白", 1, 0),
                         SpeedC135()._pick_discard(list(F_HAND), "白", 1, 0))

    def test_c141_component_wired(self):
        ch = {"count": 0, "piao": 0}
        self.assertEqual(SpeedC142()._best_giveup(list(A_HAND), 2, 0, 2, ch), "白")
        self.assertEqual(SpeedC142()._best_giveup(list(A_HAND), 2, 0, 2, ch),
                         SpeedC141()._best_giveup(list(A_HAND), 2, 0, 2, ch))
        act = SpeedC142().decide(_draw_view(A_HAND, A_DRAWN, A_MELDS))
        self.assertEqual((act.get("action"), act.get("tile")), ("discard", "白"))
        # 基线在同一盘是直接胡
        self.assertEqual(SpeedTUG().decide(_draw_view(A_HAND, A_DRAWN, A_MELDS)).get("action"), "hu")

    def test_baseline_unchanged_on_fix1(self):
        """钩子默认行为不变：SpeedTUGC 在 FIX1/FIX2 上仍是 pass。"""
        self.assertEqual(SpeedTUGC().decide(_view(*FIX1)).get("action"), "pass")
        self.assertEqual(SpeedTUGC().decide(_view(*FIX2)).get("action"), "pass")


if __name__ == "__main__":
    unittest.main()
