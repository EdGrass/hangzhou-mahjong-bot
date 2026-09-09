# -*- coding: utf-8 -*-
"""SpeedT（tie 弃牌偏好）单测——pref 分级 + 同向听选择。"""
import unittest

from bot.speedt import _pref, _best_discard_t


class TestPref(unittest.TestCase):
    def test_ranks(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "2b", "2b", "南", "白"]
        self.assertEqual(_pref("南", hand), 0)     # 孤字最优先弃
        self.assertEqual(_pref("白", hand), 4)     # 白最后弃
        self.assertEqual(_pref("2b", hand), 3)     # 拆对后置
        # 无邻孤数张（中张）
        hand2 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                 "2b", "6b", "南", "东"]
        self.assertEqual(_pref("6b", hand2), 1)    # 无邻孤中张
        # 顺子成员（邻接在手）
        hand3 = ["1w", "2w", "3w", "5w", "6w", "7w", "4b", "4b", "9t",
                 "9t", "南", "东", "白"]
        self.assertEqual(_pref("5w", hand3), 2)    # 5w 有 6w 邻 → 顺拆
        self.assertEqual(_pref("4b", hand3), 3)    # 拆对


class TestBestDiscard(unittest.TestCase):
    def test_prefers_discard_single_over_pair(self):
        # 同向听局面：保留对子（拆对后置）→ 弃牌应为孤张/顺拆而非对子
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7t", "8t", "9t",
                "2b", "2b", "5b", "1t"]
        # 弃 5b(孤) 或 1t(孤边) 或拆 2b：T 应弃孤张
        tile = _best_discard_t(hand, None, 0, 0)
        self.assertNotEqual(tile, "2b")
        self.assertIn(tile, ("5b", "1t"))


if __name__ == "__main__":
    unittest.main()
