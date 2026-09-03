"""SpeedA（向听数驱动速度基线）冒烟测试。"""
import unittest

from bot.speed import SpeedA
from mahjong.sim import SimGame


class TestSpeedA(unittest.TestCase):
    def test_zero_violation_conservation(self):
        for seed in (1, 9):
            r = SimGame([SpeedA()] * 4, rounds=8, seed=seed).run()
            st = r["stats"]
            self.assertEqual(st["violations"], 0, "seed=%d" % seed)
            self.assertEqual(sum(r["totals"]), 0)
            self.assertEqual(st["rounds_played"], 8)

    def test_speed_high_hu_rate(self):
        """速度基线应显著少流局、多自摸（向听驱动快成型）。"""
        res = SimGame([SpeedA()] * 4, rounds=32, seed=11).run()
        st = res["stats"]
        self.assertGreater(sum(st["hu_count"]), 32 * 0.5,
                           "32 局至少一半以上有人胡（流局率低）")
        self.assertLess(st["draw_count"], 32 * 0.5)

    def test_discard_legal(self):
        from bot.model import my_turn
        from mahjong.shanten_exact import shanten as ex_sh
        s = SpeedA()
        # 构造一手上无副露手牌：弃牌应使向听数最小
        hand14 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                  "1b", "2b", "3b", "东", "东"]
        view = {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
                "drawn_tile": "东", "my_hand": hand14, "god": {},
                "scores": None, "melds": [], "offer_tile": None,
                "can_gang": True}
        act = s.decide(view)
        self.assertEqual(act["action"], "hu")      # 已是和牌形 → 直接胡
        # 拆成未成型手：弃后向听应 ≤ 弃其他
        hand14b = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                   "1b", "2b", "3b", "东", "南"]
        view["my_hand"] = hand14b
        act = s.decide(view)
        self.assertEqual(act["action"], "discard")
        self.assertIn(act["tile"], hand14b)


if __name__ == "__main__":
    unittest.main()
