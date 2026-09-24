# -*- coding: utf-8 -*-
"""SpeedC141 单测：把**财飘**（爆头态弃白 = 链 +1 再 ×2）计进弃胡判据。

两个**真机盘**（2026-09-16 从 `var/replays/*` 全信息复盘抽出）：
  A) 4 面子 + 2 白、已爆头（fan_now=2）：现有判据 0.71×2 ≤ 2 ⇒ 直接胡；
     c141 看到「弃白=财飘 ⇒ 番 4」⇒ 0.71×4 > 2 ⇒ **弃白**。 ← 本候选的全部价值所在
  B) 普通弃胡盘（fan_now=1，最优弃牌 = 8w 非白）：修正前后都必须**同样弃 8w**（不误伤）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc141 import SpeedC141          # noqa: E402
from bot.speedtugc import SpeedTUGC          # noqa: E402

# A：真机盘 —— c141 应改判为「弃白（财飘）」
A_HAND = ["4t", "5t", "6t", "7b", "9b", "白", "白", "白"]
A_DRAWN = "5t"
A_MELDS = [{"type": "peng", "tile": "1t"}, {"type": "peng", "tile": "2t"}]

# B：真机盘 —— 修正前后一致，弃 8w（非白），用于证明「不误伤普通弃胡」
B_HAND = ["3b", "4b", "5b", "6w", "7w", "8b", "8w", "8w", "9b", "白", "白"]
B_DRAWN = "白"
B_MELDS = [{"type": "peng", "tile": "1t"}]


def _view(hand, drawn, melds, chain=0, piao=0, river=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": list(melds), "drawn_tile": drawn,
            "offer_tile": None, "river": list(river or []),
            "all_melds": [], "can_gang": True,
            "god": {"baotou": False, "chain_count": chain, "catch_play": False,
                    "piao_count": piao, "god_discarder_seat": -1}}


class TestSpeedC141(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc141", F)
        self.assertIsInstance(F["speedc141"](), SpeedC141)

    def test_only_difference_is_giveup_hook(self):
        self.assertIs(SpeedC141.decide, SpeedTUGC.decide)
        self.assertIsNot(SpeedC141._best_giveup, SpeedTUGC._best_giveup)

    def test_baseline_takes_the_win_on_piao_盘(self):
        """基线在 A 盘必须直接胡（0.71×2 ≤ 2）——否则本候选没有存在意义。"""
        act = SpeedTUGC().decide(_view(A_HAND, A_DRAWN, A_MELDS))
        self.assertEqual(act.get("action"), "hu")

    def test_c141_discards_white_for_piao(self):
        """c141 在 A 盘必须弃白（财飘）：番 2→4，期望 0.71×4=2.84 > 2。"""
        act = SpeedC141().decide(_view(A_HAND, A_DRAWN, A_MELDS))
        self.assertEqual(act.get("action"), "discard")
        self.assertEqual(act.get("tile"), "白")

    def test_giveup_hook_direct(self):
        """直接调钩子：同一个盘，基线 None，c141 返回白。"""
        base = SpeedTUGC()
        ch = {"count": 0, "piao": 0}
        self.assertIsNone(base._best_giveup(list(A_HAND), 2, 0, 2, ch))
        self.assertEqual(SpeedC141()._best_giveup(list(A_HAND), 2, 0, 2, ch), "白")

    def test_v33_gang_then_piao_chain(self):
        """v33 新规（09-13）：杠后补牌**不再自动结算** ⇒ 可以「拒胡 → 弃白续飘」把链叠到 2。

        盘面：杠后（chain=1）摸到和牌，手上 4 面子 + 2 白（= 杠开+爆头，fan_now=4）。
        基线：fb 用弃牌前 chain 估 → 1×2×2=4 ⇒ 0.71×4=2.84 ≤ 4 ⇒ **直接胡**；
        C141：弃白 ⇒ chain=2、piao=1 ⇒ 下一摸 fan=8 ⇒ 0.71×8=5.68 > 4 ⇒ **弃白续飘**。
        （已用服务器 /portal/api/fan_calc 核对：chain={1,0} 爆头=4；{2,1} 爆头=8。）
        """
        ch = {"count": 1, "piao": 0}
        self.assertIsNone(SpeedTUGC()._best_giveup(list(A_HAND), 2, 0, 4, ch))
        self.assertEqual(SpeedC141()._best_giveup(list(A_HAND), 2, 0, 4, ch), "白")
        v = _view(A_HAND, A_DRAWN, A_MELDS, chain=1)
        self.assertEqual((SpeedC141().decide(v) or {}).get("action"), "discard")
        v2 = _view(A_HAND, A_DRAWN, A_MELDS, chain=1)
        self.assertEqual(SpeedTUGC().decide(v2).get("action"), "hu")

    def test_normal_decline_unchanged(self):
        """B 盘（非白最优弃牌）修正前后一致：都弃 8w。"""
        ch = {"count": 0, "piao": 0}
        self.assertEqual(SpeedTUGC()._best_giveup(list(B_HAND), 1, 0, 1, ch), "8w")
        self.assertEqual(SpeedC141()._best_giveup(list(B_HAND), 1, 0, 1, ch), "8w")

    def test_no_decline_option_returns_none(self):
        """无爆头形可弃 ⇒ 两者都返回 None（继续胡）。"""
        hand = ["1t", "2t", "3t", "4t", "5t", "6t", "7t", "8t", "9t", "东", "东", "东", "南", "南"]
        ch = {"count": 0, "piao": 0}
        self.assertIsNone(SpeedTUGC()._best_giveup(list(hand), 0, 0, 1, ch))
        self.assertIsNone(SpeedC141()._best_giveup(list(hand), 0, 0, 1, ch))


if __name__ == "__main__":
    unittest.main()
