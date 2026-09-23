# -*- coding: utf-8 -*-
"""speedc152（分档对数奖励）单测：语义与设计一致、单调性有护栏、主键仍是向听。"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc150 import SpeedC150                                    # noqa: E402
from bot.speedc152 import (SpeedC152, W_GRADED, _pair_count,           # noqa: E402
                           _pick_discard_graded, _route_bonus)
from mahjong.shanten_exact import shanten as exact_shanten             # noqa: E402


class TestGradedBonus(unittest.TestCase):
    """★ 方向护栏：分档权重必须**单调不增**，且 pc>=3 无加成（依据 §9.26 的实测曲线）。"""

    def test_weights_are_monotone(self):
        w = [W_GRADED.get(k, 0.0) for k in range(3)]
        self.assertGreater(w[0], w[1], "pc=0 的权重必须高于 pc=1（实测 100% vs 33.8%）")
        self.assertGreater(w[1], w[2], "pc=1 的权重必须高于 pc=2（实测 33.8% vs 29.4%）")
        self.assertGreater(w[2], 0.0, "pc=2 仍应有一个小加成")

    def test_no_bonus_from_three_pairs_up(self):
        for n in (3, 4, 5):
            hand = []
            for i in range(n):
                hand += ["%dw" % (i + 1)] * 2
            hand += ["东", "南", "西"]
            self.assertEqual(_pair_count(hand), n)
            self.assertEqual(_route_bonus(hand, "x"), 0.0, "pc>=3 不应有加成")

    def test_bonus_values(self):
        self.assertEqual(_route_bonus(["1w", "2w", "3w", "东"], "x"), W_GRADED[0])
        self.assertEqual(_route_bonus(["1w", "1w", "3w", "东"], "x"), W_GRADED[1])
        self.assertEqual(_route_bonus(["1w", "1w", "2w", "2w", "东"], "x"), W_GRADED[2])

    def test_sign_is_positive_for_discard(self):
        src = inspect.getsource(_pick_discard_graded)
        self.assertIn("u += _route_bonus", src,
                      "分档奖励必须是**奖励弃牌**方向（u 增大）；key 用 −u，写成 −= 会把方向打反")


class TestWiring(unittest.TestCase):
    def test_subclass_and_hook(self):
        s = SpeedC152()
        self.assertIsInstance(s, SpeedC150)          # 与 c151 同父：继承 C036/C135 全套
        self.assertEqual(s.name, "speedc152")
        self.assertTrue(hasattr(s, "_best_giveup"), "必须继承 C036 的弃胡换爆头")
        self.assertIn("_pick_discard", SpeedC152.__dict__, "必须覆盖弃牌钩子（单变量）")

    def test_registered_in_run_bot(self):
        # 只读源码判断注册（避免 import run_bot 触发副作用）
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"speedc152"', src, "必须在 run_bot.STRATEGY_FACTORIES 注册")

    def test_shanten_is_still_primary(self):
        hand = ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "南", "西"]
        pick = _pick_discard_graded(list(hand), "西", 0, 0)
        self.assertIn(pick, hand, "必须返回手牌中的一张")
        rem = list(hand)
        rem.remove(pick)
        got = exact_shanten(rem, qidui=True, exposed_melds=0, gangs=0)
        best = min(exact_shanten([x for j, x in enumerate(hand) if j != i], qidui=True,
                                 exposed_melds=0, gangs=0)
                   for i in range(len(hand)) if hand[i] in set(hand))
        self.assertEqual(got, best, "向听必须仍是最小（主键不许被加成压过）")


if __name__ == "__main__":
    unittest.main()
