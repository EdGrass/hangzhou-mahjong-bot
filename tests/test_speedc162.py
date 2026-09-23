# -*- coding: utf-8 -*-
"""speedc162（保对子档）单测：与 c152 **方向相反**、主键仍是向听、且必须继承 C036。

本档的依据与冲突都写在 `bot/speedc162.py` 里；这里只钉不变量：
  ① `KP_KEEP` 必须**单调不减**（越多对子越优），且 pc≥5（七对线）给满；
  ② 路线加成必须是**奖励**方向（`u += ...`，key 用 −u）；
  ③ 主键仍是向听（`if s != smin: continue`）；
  ④ 与 c152 同父（继承 C036/C135），不许旁路 `_best_giveup`。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc150 import SpeedC150                                     # noqa: E402
from bot.speedc152 import SpeedC152                                     # noqa: E402
from bot.speedc162 import (KP_KEEP, SpeedC162, _pair_count,             # noqa: E402
                           _pick_discard_keep_pairs, _route_bonus_keep)


class TestKeepPairsBonus(unittest.TestCase):
    def test_weights_monotone_nondecreasing(self):
        w = [KP_KEEP.get(k, 0.0) for k in range(6)]
        for i in range(5):
            self.assertLessEqual(w[i], w[i + 1], "保对子档必须是**越多对子越大**（与 c152 相反）")
        self.assertEqual(w[5], max(w), "pc>=5（七对线）应给满")

    def test_opposite_direction_to_c152(self):
        from bot.speedc152 import W_GRADED
        self.assertGreater(KP_KEEP[3], W_GRADED.get(3, 0.0), "pc=3 时两档方向必须相反")
        self.assertGreater(KP_KEEP[2], W_GRADED.get(2, 0.0))

    def test_bonus_values(self):
        self.assertEqual(_route_bonus_keep(["1w", "2w", "3w", "东"]), KP_KEEP[0])
        self.assertEqual(_route_bonus_keep(["1w", "1w", "3w", "东"]), KP_KEEP[1])
        self.assertEqual(_route_bonus_keep(["1w", "1w", "2w", "2w", "东"]), KP_KEEP[2])
        hand5 = []
        for i in range(5):
            hand5 += ["%dw" % (i + 1)] * 2
        self.assertEqual(_pair_count(hand5), 5)
        self.assertEqual(_route_bonus_keep(hand5), KP_KEEP[5])

    def test_sign_and_primary_key(self):
        src = inspect.getsource(_pick_discard_keep_pairs)
        self.assertIn("u += _route_bonus_keep", src, "必须是奖励方向（key 用 −u）")
        self.assertIn("if s != smin", src, "向听必须仍是主键（下行有界）")


class TestWiring(unittest.TestCase):
    def test_subclass_and_hook(self):
        s = SpeedC162()
        self.assertIsInstance(s, SpeedC150)
        self.assertEqual(s.name, "speedc162")
        self.assertTrue(hasattr(s, "_best_giveup"), "必须继承 C036 弃胡换爆头")
        self.assertIn("_pick_discard", SpeedC162.__dict__, "必须覆盖弃牌钩子（单变量）")

    def test_not_same_class_as_c152(self):
        self.assertIsNot(type(SpeedC162()), type(SpeedC152()))

    def test_registered_in_run_bot(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"speedc162"', src, "必须在 run_bot.STRATEGY_FACTORIES 注册")


if __name__ == "__main__":
    unittest.main()
