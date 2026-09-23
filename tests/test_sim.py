"""本地模拟器单测（SpeedBase 全席）：不变量 + 确定性 + 非法动作兜底。"""
import unittest

from bot.speed import SpeedBase
from mahjong.sim import SimGame


def _speed4():
    return [SpeedBase()] * 4


class TestSimInvariants(unittest.TestCase):
    def _check(self, res, rounds):
        st = res["stats"]
        self.assertEqual(sum(res["totals"]), 0, "总分必须守恒")
        self.assertEqual(st["rounds_played"], rounds)
        self.assertEqual(sum(st["hu_count"]) + st["draw_count"], rounds,
                         "胡+流局 == 局数")
        for i in range(4):
            self.assertGreaterEqual(st["hu_count"][i], 0)

    def test_speed_four(self):
        for seed in (1, 2, 3):
            res = SimGame(_speed4(), rounds=8, seed=seed).run()
            self._check(res, 8)
            self.assertEqual(res["stats"]["violations"], 0, "speedBase 不应违规")
            self.assertEqual(res["stats"]["fallbacks"], 0)

    def test_deterministic(self):
        a = SimGame(_speed4(), rounds=8, seed=42).run()
        b = SimGame(_speed4(), rounds=8, seed=42).run()
        self.assertEqual(a, b)

    def test_illegal_hu_counted_and_game_finishes(self):
        class Bad(SpeedBase):
            def decide(self, view):
                from bot.model import my_turn
                if my_turn(view):
                    return {"action": "hu", "tile": ""}   # 无脑胡（多数非法）
                return None

        res = SimGame([Bad()] + _speed4()[1:], rounds=8, seed=7).run()
        st = res["stats"]
        self.assertGreaterEqual(st["violations"], 1, "非法胡应被记录并兜底")
        self.assertEqual(st["rounds_played"], 8)


class TestSimMakesWins(unittest.TestCase):
    def test_speed_hits_wins(self):
        """大量局数下应出现胡牌且流局率低（速度基线特征）。"""
        res = SimGame(_speed4(), rounds=16, seed=2026).run()
        st = res["stats"]
        self.assertGreater(sum(st["hu_count"]), 0)
        self.assertLess(st["draw_count"], 32 * 0.5)


if __name__ == "__main__":
    unittest.main()

