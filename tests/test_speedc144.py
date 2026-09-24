# -*- coding: utf-8 -*-
"""SpeedC144 单测：明杠门控（第 4 张是死牌就杠，按路线判断而不是"向听必须下降"）。

真机依据（2026-09-16 实测）：
  - 603/603 个 gang 事件后紧跟同座位 `tile_drawn(gang_replenish=true)` ⇒ 明杠 = 白赚一次摸牌；
  - 3,716 个杠的进度 p50=0.67（我们的采样分母含保留区，不能据此推断"晚盘不限杠"）；
    **指南 §1.1 明确「最后 10 墩（20 张）之内禁止杠牌」** ⇒ 明杠也必须跟自杠同一道河长守卫
    （`SELF_GANG_MAX_RIVER`；宁可保守，避免 409 丢机会）；
  - 我方 杠/轮 0.010 vs 全场 0.024–0.077；「三张在手 + 别家打第 4 张」窗口 ≈2.9 次/场（30 场实测 88 次）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc144 import SpeedC144          # noqa: E402
from bot.speedtugc import SpeedTUGC          # noqa: E402

MELD1 = [{"type": "peng", "tile": "1t"}]


def _view(hand, offer, melds=None, catch_play=False, river_len=6):
    return {"seat": 0, "phase": "response_peng", "turn": 1, "responding_seats": [0],
            "my_hand": list(hand), "melds": list(melds or []), "drawn_tile": None,
            "offer_tile": offer, "river": [], "all_melds": [], "can_gang": True,
            "river_len": river_len,
            "god": {"baotou": False, "chain_count": 0, "catch_play": catch_play,
                    "piao_count": 0, "god_discarder_seat": -1}}


# 已有副露 + 手上 3 张 ⇒ 应杠
H_MELDED = ["2b", "2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白"]
# 门清但七对路线仍然可行（5 对 + 1 刻子）⇒ 应保留路线、不杠
H_QIDUI = ["2b", "2b", "2b", "3b", "3b", "5t", "5t", "6t", "6t", "7w", "7w", "8t", "8t"]
# 门清且一般形已听（123t/456t/789t + 5b5b5b + 孤东）⇒ 应杠
H_TENPAI = ["5b", "5b", "5b", "1t", "2t", "3t", "4t", "5t", "6t", "7t", "8t", "9t", "东"]


class TestSpeedC144(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc144", F)
        self.assertIsInstance(F["speedc144"](), SpeedC144)

    def test_only_hook_changed(self):
        self.assertIs(SpeedC144.decide, SpeedTUGC.decide)
        self.assertIsNot(SpeedC144._want_claim, SpeedTUGC._want_claim)

    def test_melded_hand_takes_gang(self):
        """已有副露 ⇒ 七对不可能 ⇒ 第 4 张是死牌，收下（基线这里必然 pass）。"""
        v = _view(H_MELDED, "2b", MELD1)
        self.assertTrue(SpeedC144()._want_ming_gang(v))
        self.assertEqual(SpeedTUGC().decide(v).get("action"), "pass")
        self.assertEqual(SpeedC144().decide(v).get("action"), "gang")
        self.assertEqual(SpeedC144().decide(v).get("tile"), "2b")

    def test_closed_hand_keeps_qidui_route(self):
        """门清且七对仍可行 ⇒ 不收（保留路线）。"""
        v = _view(H_QIDUI, "2b")
        self.assertFalse(SpeedC144()._want_ming_gang(v))
        self.assertNotEqual(SpeedC144().decide(v).get("action"), "gang")

    def test_tenpai_closed_hand_takes_gang(self):
        """门清但一般形已听 ⇒ 收（不再为七对让路）。"""
        v = _view(H_TENPAI, "5b")
        self.assertTrue(SpeedC144()._want_ming_gang(v))

    def test_catch_play_blocks_gang(self):
        """抓打圈内别家禁明杠（指南）——即使其余条件都满足。"""
        v = _view(H_MELDED, "2b", MELD1, catch_play=True)
        self.assertFalse(SpeedC144()._want_ming_gang(v))

    def test_fewer_than_three_returns_false(self):
        v = _view(["2b", "2b", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "白", "东"], "2b", MELD1)
        self.assertFalse(SpeedC144()._want_ming_gang(v))

    def test_white_cannot_be_ganged(self):
        v = _view(["白", "白", "白", "3t", "5t", "6w", "7t", "7w", "8w", "9w", "1b"], "白", MELD1)
        self.assertFalse(SpeedC144()._want_ming_gang(v))


if __name__ == "__main__":
    unittest.main()

class TestLateKongGuard(unittest.TestCase):
    """指南 §1.1：最后 10 墩（20 张）之内禁止杠牌 ⇒ 明杠也要跟自杠同一道河长守卫。"""

    def test_ming_gang_refused_when_river_too_long(self):
        from bot.speedtugc import SpeedTUGC
        v = _view(H_MELDED, "2b", MELD1, river_len=SpeedTUGC.SELF_GANG_MAX_RIVER)
        self.assertFalse(SpeedC144()._want_ming_gang(v))
        self.assertNotEqual((SpeedC144().decide(v) or {}).get("action"), "gang")

    def test_ming_gang_allowed_early(self):
        v = _view(H_MELDED, "2b", MELD1, river_len=10)
        self.assertTrue(SpeedC144()._want_ming_gang(v))

    def test_river_len_falls_back_to_river_list(self):
        v = _view(H_MELDED, "2b", MELD1)
        v.pop("river_len", None)
        v["river"] = ["1t"] * 60
        self.assertFalse(SpeedC144()._want_ming_gang(v))
