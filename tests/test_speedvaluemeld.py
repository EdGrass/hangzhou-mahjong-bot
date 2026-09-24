# -*- coding: utf-8 -*-
"""`bot/speedvaluemeld.SpeedValueMeld` 契约测试（R1190）。

役 4 候选必须能归因到"**只多一条：选择性副露**"，所以四条不变量要钉住：

  ① **不否决**：基线 `SpeedValue._want_claim` 说"要"时，候选必须也说"要"（单向增加、下行有界）；
  ② **与 `SpeedC156` 行为等价**：同一 view 下本臂的 `_want_claim` 必须等于 `bot/speedc156.SpeedC156._want_claim`
     （两边 super 链都落在 `SpeedC144._want_claim`，网也是同一个 c121 网）⇒ 防"照抄的 12 行"漂移；
  ③ **模型缺失 ⇒ 零行为变化**：`_mnet=None` 时与基线逐位一致；
  ④ **只动索取层**：类不定义 `_pick_discard`（出牌解析必须仍来自 `SpeedValue`）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc156 import SpeedC156                        # noqa: E402
from bot.speedvaluemeld import SpeedValueMeld              # noqa: E402
from bot.speedvalue import SpeedValue                      # noqa: E402


def _view(hand, offer, kind="peng", melds=None, river=None, all_melds=None):
    return {"seat": 0, "phase": "response_peng" if kind in ("peng", "gang_ming") else "response_chi",
            "turn": 3, "responding_seats": [0], "my_hand": list(hand), "melds": list(melds or []),
            "drawn_tile": None, "offer_tile": offer, "river": list(river or []),
            "all_melds": list(all_melds or []), "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


CASES = [
    _view(["1w", "1w", "2w", "3w", "4w", "5w", "6w", "7b", "8b", "1t", "2t", "3t", "5t"], "1w", "peng"),
    _view(["2w", "3w", "4w", "5w", "6w", "7b", "8b", "1t", "2t", "3t", "5t", "9t", "9t"], "3w", "chi"),
    _view(["5w", "5w", "6w", "7w", "2b", "3b", "4b", "8t", "9t", "1t", "1t", "3t", "7t"], "5w", "peng"),
    _view(["1t", "2t", "3t", "4t", "5t", "6t", "7t", "8t", "9t", "1w", "2w", "3w", "白"], "6t", "chi"),
    _view(["3b", "3b", "4b", "5b", "6b", "7b", "8b", "9b", "1w", "1w", "2w", "3w", "中", "中"], "3b", "peng"),
]


class SpeedValueMeldTest(unittest.TestCase):
    def setUp(self):
        self.base = SpeedValue()
        self.cand = SpeedValueMeld()
        self.c156 = SpeedC156()

    # ① 不否决
    def test_never_vetoes_base_claim(self):
        for v in CASES:
            kind = "peng" if v["phase"] == "response_peng" else "chi"
            if self.base._want_claim(v, kind):
                self.assertTrue(self.cand._want_claim(v, kind),
                                "候选否决了基线会要的窗口（违反单向增加）")

    # ② 与 SpeedC156 等价
    def test_equivalent_to_speedc156(self):
        for v in CASES:
            kind = "peng" if v["phase"] == "response_peng" else "chi"
            self.assertEqual(self.cand._want_claim(v, kind), self.c156._want_claim(v, kind),
                             "与 SpeedC156 的索取判据不一致（照抄的逻辑漂移了）")

    # ③ 模型缺失 ⇒ 与基线逐位一致
    def test_missing_model_is_identity(self):
        self.cand._mnet = None
        for v in CASES:
            kind = "peng" if v["phase"] == "response_peng" else "chi"
            self.assertEqual(self.cand._want_claim(v, kind), self.base._want_claim(v, kind))

    # ④ 只动索取层
    def test_discard_layer_untouched(self):
        self.assertNotIn("_pick_discard", SpeedValueMeld.__dict__)
        for c in SpeedValueMeld.__mro__:
            if "_pick_discard" in c.__dict__:
                self.assertEqual(c.__name__, "SpeedValue")
                break

    # 模型确实加载（起役前提）
    def test_model_loaded(self):
        self.assertIsNotNone(self.cand._mnet)


if __name__ == "__main__":
    unittest.main()
