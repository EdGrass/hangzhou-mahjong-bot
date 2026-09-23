# -*- coding: utf-8 -*-
"""C064 SpeedQ2 单元测试：特征、回退与快速动作评分。"""
import os
import unittest

from mahjong.sim import make_view

import bot.speedq2 as m


HAND = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
        "9w", "1b", "2b", "3b", "东", "南"]


class _FakeModel:
    def score(self, rows):
        return [0.1] * len(rows), [0.2] * len(rows)


class TestSpeedQ2(unittest.TestCase):
    def test_state_feature_shape(self):
        f = m._state_feat(HAND[:13], 0, 0)
        self.assertEqual(len(f), 43)

    def test_missing_model_falls_back(self):
        st = m.SpeedQ2(model_path=os.path.join("var", "__no_such_c064__"))
        view = make_view(0, "draw", 0, HAND, melds=[], river=[],
                         all_melds=[[], [], [], []], dealer=0)
        act = st.decide(view)
        self.assertEqual(act.get("action"), "discard")
        self.assertIn(act.get("tile"), HAND)

    def test_scores_cover_candidates(self):
        st = m.SpeedQ2(model_path=os.path.join("var", "__no_such_c064__"), tp_weight=0.25)
        st.model = _FakeModel()
        scores = st._scores(HAND, ["1w", "2w"], 0, 0)
        self.assertEqual(set(scores), {"1w", "2w"})
        self.assertAlmostEqual(scores["1w"], 0.1 + 0.25 * 0.2)


if __name__ == "__main__":
    unittest.main()