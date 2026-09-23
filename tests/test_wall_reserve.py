"""C003 评估口径参数测试：sim wall_reserve 可配置且行为符合预期。

- 相同 seed/配置 → 确定性一致（含 wall_reserve）；
- wall_reserve=60（短局校准）比默认 20 产生更多流局（牌墙更早耗尽）。
"""
import unittest

from bot.speed import SpeedBase
from mahjong.sim import SimGame


def _sp():
    return [SpeedBase()] * 4


class TestWallReserve(unittest.TestCase):
    def test_deterministic_with_reserve(self):
        a = SimGame(_sp(), rounds=8, seed=42, wall_reserve=60).run()
        b = SimGame(_sp(), rounds=8, seed=42, wall_reserve=60).run()
        self.assertEqual(a, b)

    def test_default_unchanged(self):
        a = SimGame(_sp(), rounds=8, seed=7).run()
        b = SimGame(_sp(), rounds=8, seed=7, wall_reserve=None).run()
        self.assertEqual(a, b)

    def test_reserve60_more_draws(self):
        d20 = d60 = 0
        for seed in (3, 11, 29):
            r20 = SimGame(_sp(), rounds=16, seed=seed).run()
            r60 = SimGame(_sp(), rounds=16, seed=seed, wall_reserve=60).run()
            d20 += r20["stats"]["draw_count"]
            d60 += r60["stats"]["draw_count"]
            self.assertEqual(sum(r60["totals"]), 0, "守恒 seed=%d" % seed)
            self.assertEqual(r60["stats"]["violations"], 0)
        self.assertGreater(d60, d20,
                           "保留 60（短局）应显著更多流局: %d vs %d" % (d60, d20))


if __name__ == "__main__":
    unittest.main()
