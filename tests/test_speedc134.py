# -*- coding: utf-8 -*-
"""SpeedC134 单测：默认关闭（speedtugc 行为不变）；开启后**只在该杠时杠**。

注意 `view["turn"]` 是**行动座位号**（my_turn 判据 turn==seat），不是巡次——
所以时间守卫用 `river_len`（本局公开弃牌总数，摸牌数的廉价代理）。
抓打圈按指南：非豁免方**只能暗杠**（不能吃/碰/明杠），打财神者本人不受限。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedtugc import SpeedTUGC           # noqa: E402
from bot.speedc134 import SpeedC134           # noqa: E402


def _view(hand, melds=None, river_len=6, god=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": list(melds or []), "drawn_tile": hand[-1],
            "offer_tile": None, "river_len": river_len,
            "god": god or {"baotou": False, "chain_count": 0, "catch_play": False,
                           "god_discarder_seat": -1},
            "all_melds": []}


def _peng(tile):
    return {"type": "peng", "tile": tile, "tiles": [tile] * 3}


BU_HAND = ["白", "3b", "1b", "7t", "6t", "9t", "3t", "5t", "4b", "5b", "6t"]
AN_HAND = ["1w", "1w", "1w", "1w", "2w", "3w", "4w", "5b", "6b", "7b", "1t"]
AN_MELDS = [_peng("东")]
QIDUI_HAND = ["1w", "1w", "1w", "1w", "2w", "2w", "3w", "3w",
              "4b", "4b", "5b", "5b", "6t", "7b"]


class TestSpeedC134(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc134", F)
        self.assertIsInstance(F["speedc134"](), SpeedC134)

    def test_default_is_off(self):
        """speedtugc 必须保持「从不自杠」——否则会悄悄改变正在跑的 A/B 基线。"""
        self.assertFalse(SpeedTUGC.SELF_GANG)
        self.assertFalse(SpeedTUGC().SELF_GANG)
        self.assertEqual((SpeedTUGC().decide(_view(BU_HAND, [_peng("9t")])) or {}).get("action"),
                         "discard")

    def test_bu_gang_when_qidui_impossible(self):
        act = SpeedC134().decide(_view(BU_HAND, [_peng("9t")]))
        self.assertEqual(act.get("action"), "gang")
        self.assertEqual(act.get("tile"), "9t")

    def test_keeps_qidui_route(self):
        """门清且七对路线是活的时候**不杠**（4 张 1w 是豪华七对的两对）。"""
        self.assertEqual((SpeedC134().decide(_view(QIDUI_HAND)) or {}).get("action"), "discard")

    def test_no_gang_without_four(self):
        hand = ["1w", "2w", "3w", "4b", "5b", "6b", "1t", "2t", "3t",
                "7w", "8w", "9w", "东", "南"]          # 4 面子 + 孤张，未胡
        self.assertEqual((SpeedC134().decide(_view(hand)) or {}).get("action"), "discard")

    def test_late_river_guard(self):
        """接近最后 10 墩（river_len 到线）时不杠，避免被服务端 409。"""
        v = _view(BU_HAND, [_peng("9t")], river_len=SpeedTUGC.SELF_GANG_MAX_RIVER)
        self.assertEqual((SpeedC134().decide(v) or {}).get("action"), "discard")

    def test_catch_play_non_exempt_only_an_gang(self):
        """抓打圈非豁免方：补杠不做、暗杠允许。"""
        opp = {"baotou": False, "chain_count": 0, "catch_play": True,
               "god_discarder_seat": 1}
        self.assertEqual(
            (SpeedC134().decide(_view(BU_HAND, [_peng("9t")], god=opp)) or {}).get("action"),
            "discard")
        act = SpeedC134().decide(_view(AN_HAND, AN_MELDS, god=opp))
        self.assertEqual(act.get("action"), "gang")
        self.assertEqual(act.get("tile"), "1w")

    def test_catch_play_exempt_unrestricted(self):
        """打财神者本人不受限 ⇒ 补杠照做。"""
        mine = {"baotou": False, "chain_count": 0, "catch_play": True,
                "god_discarder_seat": 0}
        self.assertEqual(
            (SpeedC134().decide(_view(BU_HAND, [_peng("9t")], god=mine)) or {}).get("action"),
            "gang")


if __name__ == "__main__":
    unittest.main()
