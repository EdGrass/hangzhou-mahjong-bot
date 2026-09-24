# -*- coding: utf-8 -*-
"""`bot/speedvaluebcmeld.SpeedValueBCMeld` 契约测试（R1228）——**两层叠加的组合臂**。

钉住四件事：
  ① 两层**解析正确**：`_pick_discard` 来自 `SpeedValueBC`、`_want_claim` 来自 `SpeedValueMeld`；
  ② 两个模型都加载（BC 154 维网 + 81 维副露网）；
  ③ **层间独立**：出牌层行为 == 单轴 BC 臂；索取层行为 == 单轴 meld 臂（同 view 同结论）；
  ④ 任一模型缺失 ⇒ 该层**自动退化**为基线（不报错、不半残）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                      # noqa: E402
from bot.speedvaluebc import SpeedValueBC                  # noqa: E402
from bot.speedvaluebcmeld import SpeedValueBCMeld          # noqa: E402
from bot.speedvaluemeld import SpeedValueMeld              # noqa: E402


def _draw_view(hand, drawn=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": [], "all_melds": [],
            "river": [], "river_len": 0,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


def _claim_view(hand, offer, kind="peng"):
    return {"seat": 0, "phase": "response_peng", "turn": 3, "responding_seats": [0],
            "my_hand": list(hand), "melds": [], "drawn_tile": None, "offer_tile": offer,
            "river": [], "river_len": 0, "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


HAND = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']
CLAIM_HAND = ['3b', '3b', '4b', '5b', '6b', '7b', '8b', '9b', '1w', '1w', '2w', '3w', '中', '中']


class ComboArmTest(unittest.TestCase):
    def setUp(self):
        self.combo = SpeedValueBCMeld()

    def test_layer_resolution(self):
        for c in type(self.combo).__mro__:
            if "_pick_discard" in c.__dict__:
                self.assertEqual(c.__name__, "SpeedValueBC")
                break
        for c in type(self.combo).__mro__:
            if "_want_claim" in c.__dict__:
                self.assertEqual(c.__name__, "SpeedValueMeld")
                break

    def test_both_models_loaded(self):
        self.assertIsNotNone(self.combo.model)
        self.assertIsNotNone(self.combo._mnet)

    def test_discard_layer_matches_single_axis(self):
        bc = SpeedValueBC()
        v = _draw_view(HAND, None)
        self.assertEqual(self.combo._pick_discard(list(HAND), None, 0, 0, view=v),
                         bc._pick_discard(list(HAND), None, 0, 0, view=v))

    def test_claim_layer_matches_single_axis(self):
        md = SpeedValueMeld()
        v = _claim_view(CLAIM_HAND, "3b")
        self.assertEqual(self.combo._want_claim(v, "peng"), md._want_claim(v, "peng"))

    def test_missing_models_degrade_independently(self):
        base = SpeedValue()
        v = _draw_view(HAND, None)
        self.combo.model = None                      # 缺 BC ⇒ 出牌层退化
        self.assertEqual(self.combo._pick_discard(list(HAND), None, 0, 0, view=v),
                         base._pick_discard(list(HAND), None, 0, 0, view=v))
        self.combo._mnet = None                      # 缺副露网 ⇒ 索取层退化
        v2 = _claim_view(CLAIM_HAND, "3b")
        self.assertEqual(self.combo._want_claim(v2, "peng"), base._want_claim(v2, "peng"))

    def test_bc_path_really_runs_and_updates_stats(self):
        """★ R1228 回归：BC 路径必须**真的跑**（不能静默兜底成纯进张）。

        手法：把 BC 网换成"永远偏好最后一张候选"的桩 ⇒ 组合臂必须采用它，且 `stats.used` 增加。
        这一条正是当初漏 `self.stats` 时会红的测试（缺属性 ⇒ 异常 ⇒ 上层兜底成 _best_discard）。
        """
        from bot.speedt import _best_discard_t

        class _Stub:
            def score(self, rows):
                return [0.0] * (len(rows) - 1) + [1.0]

        # 该手在"弃后最小向听"层有 2 张并列（5w / 9b）⇒ 模型才有得选；
        # 只有 1 张并列时 `_bc_pick` 按设计直接返回基线、不写 stats，不能用来测"真跑"。
        TWO = ['2b', '3b', '4b', '6t', '7t', '8t', '5w', '5w', '9b', '1t', '1t', '3w', '4w', '白']
        self.combo.model = _Stub()
        v = _draw_view(TWO, None)
        got = self.combo._pick_discard(list(TWO), None, 0, 0, view=v)
        self.assertGreaterEqual(self.combo.stats.get("used", 0), 1,
                                "BC 路径没有真正执行（stats.used 未增加）")
        self.assertIn(got, TWO)
        self.assertGreaterEqual(self.combo.stats.get("changed", 0), 1,
                                "桩模型偏好另一张时组合臂应当改打（changed 未增加）")


if __name__ == "__main__":
    unittest.main()
