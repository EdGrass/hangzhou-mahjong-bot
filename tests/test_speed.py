"""SpeedA（向听数驱动速度基线）冒烟与稳定性测试。"""
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
        res = SimGame([SpeedA()] * 4, rounds=16, seed=11).run()
        st = res["stats"]
        self.assertGreater(sum(st["hu_count"]), 16 * 0.5,
                           "32 局至少一半以上有人胡")
        self.assertLess(st["draw_count"], 16 * 0.5)

    def test_discard_legal(self):
        from bot.model import my_turn
        s = SpeedA()
        hand14 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                  "1b", "2b", "3b", "东", "东"]
        view = {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
                "drawn_tile": "东", "my_hand": hand14, "god": {},
                "scores": None, "melds": [], "offer_tile": None,
                "can_gang": True}
        act = s.decide(view)
        self.assertEqual(act["action"], "hu")      # 已是和牌形 → 直接胡
        hand14b = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                   "1b", "2b", "3b", "东", "南"]
        view["my_hand"] = hand14b
        act = s.decide(view)
        self.assertEqual(act["action"], "discard")
        self.assertIn(act["tile"], hand14b)


if __name__ == "__main__":
    unittest.main()

