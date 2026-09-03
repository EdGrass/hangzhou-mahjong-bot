"""本地模拟器单测：不变量 + 确定性 + 非法动作兜底。"""
import unittest

from bot.heuristic import HeuristicA
from bot.strategy import NaiveStrategy
from mahjong.sim import SimGame


def _naive4():
    return [NaiveStrategy()] * 4


def _heur4():
    return [HeuristicA()] * 4


class TestSimInvariants(unittest.TestCase):
    def _check(self, res, rounds):
        st = res["stats"]
        self.assertEqual(sum(res["totals"]), 0, "总分必须守恒")
        self.assertEqual(st["rounds_played"], rounds)
        self.assertEqual(sum(st["hu_count"]) + st["draw_count"], rounds,
                         "胡+流局 == 局数")
        for i in range(4):
            self.assertGreaterEqual(st["hu_count"][i], 0)
            self.assertGreaterEqual(st["fan_total"][i], 0)

    def test_naive_four(self):
        for seed in (1, 2, 3):
            res = SimGame(_naive4(), rounds=8, seed=seed).run()
            self._check(res, 8)
            self.assertEqual(res["stats"]["violations"], 0, "naive 不应违规")
            self.assertEqual(res["stats"]["fallbacks"], 0, "naive 每次都出牌")

    def test_heur_four(self):
        for seed in (4, 5):
            res = SimGame(_heur4(), rounds=16, seed=seed).run()
            self._check(res, 16)
            self.assertEqual(res["stats"]["violations"], 0, "heuristicA 不应违规")

    def test_deterministic(self):
        a = SimGame(_heur4(), rounds=8, seed=42).run()
        b = SimGame(_heur4(), rounds=8, seed=42).run()
        self.assertEqual(a, b)

    def test_illegal_hu_counted_and_game_finishes(self):
        class Bad(HeuristicA):
            def decide(self, view):
                from bot.model import my_turn
                if my_turn(view):
                    return {"action": "hu", "tile": ""}   # 无脑胡（多数非法）
                return None

        res = SimGame([Bad()] + _naive4()[1:], rounds=8, seed=7).run()
        st = res["stats"]
        self.assertGreaterEqual(st["violations"], 1, "非法胡应被记录并兜底")
        self.assertEqual(st["rounds_played"], 8, "违规不阻断对局")


class TestSimMakesWins(unittest.TestCase):
    def test_heuristic_hits_wins_over_many_rounds(self):
        """大量局数下应出现胡牌（非零胡率），验证 hu 路径可用。"""
        res = SimGame(_heur4(), rounds=64, seed=2026).run()
        st = res["stats"]
        self.assertGreater(sum(st["hu_count"]), 0, "64 局应至少出现一次自摸")
        self.assertGreater(max(st["fan_total"]), 0)


if __name__ == "__main__":
    unittest.main()
