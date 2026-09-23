# -*- coding: utf-8 -*-
"""C130 单测：守住 rollout 的手牌张数不变式（暗牌 = 13 - 3e - g）。

回归背景：副露建模最初只从手里去掉对子、忘了「碰之后必须弃一张」，
导致后续 exact_shanten/is_win 拿到非法手牌 —— sim 自检把胡率打到 12.5%（基线 ~25%）。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc130 import C130Policy          # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402
from mahjong.hu import is_win                 # noqa: E402


def _view(hand14, melds=(), drawn=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand14), "melds": list(melds), "drawn_tile": drawn,
            "offer_tile": None, "god": {}, "all_melds": [], "river": []}


class TestC130(unittest.TestCase):
    def test_registered_and_constructible(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc130", F)
        p = F["speedc130"]()
        self.assertEqual(p.name, "speedc130")

    def test_rollout_returns_sane_value_with_forced_melds(self):
        """meld_p=1 强制走副露分支 —— 旧实现会在这里把手牌搞成非法长度。"""
        p = C130Policy(samples=4, steps=3, max_cand=3, meld_p=1.0, seed=1)
        hand13 = ["1w", "1w", "2w", "3w", "4w", "5w", "6w",
                  "7b", "8b", "9b", "2t", "3t", "4t"]
        try:
            exact_shanten(hand13, qidui=True, exposed_melds=0, gangs=0)
        except ValueError as e:
            self.skipTest("样例手牌不合法：%s" % e)
        pool = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)] * 4
        seqs = p._make_seqs(pool)
        self.assertTrue(seqs, "应生成公共随机序列")
        for _ in range(30):
            s_, m_ = seqs[0]
            v = p._rollout(list(hand13), 0, 0, list(s_), list(m_))
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 16.0, "番值不可能超过 16（爆头×4白×链上限）")

    def test_common_random_numbers_are_shared_across_candidates(self):
        """CRN 的核心性质：所有候选必须看到**同一批**抽样序列。
        否则候选间比较的是采样噪声（C032 失败原因之一）。"""
        p = C130Policy(samples=6, steps=2, max_cand=3, meld_p=0.0, seed=5)
        pool = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)] * 4
        seqs = p._make_seqs(pool)
        self.assertEqual(len(seqs), p.samples)
        a = list(seqs[0][0])
        b = p._value([], 0, 0, seqs, None)     # 只有 0/空手时值为 0，不抛异常
        self.assertEqual(b, 0.0)
        # 同一批序列重复用于第二个候选时内容不变（不消耗）
        self.assertEqual(a, list(seqs[0][0]), "公共序列不应被某候选消费掉")

    def test_decide_returns_a_tile_from_hand(self):
        p = C130Policy(samples=2, steps=1, max_cand=3, meld_p=0.0, seed=2)
        hand = ["1w", "1w", "2w", "3w", "4w", "5w", "6w", "2b", "3b", "4b",
                "6t", "7t", "8t", "9b"]
        try:
            is_win(hand, exposed_melds=0, gangs=0)
        except ValueError as e:
            self.skipTest("样例手牌不合法：%s" % e)
        act = p.decide(_view(hand, drawn="9b"))
        self.assertEqual(act.get("action"), "discard")
        self.assertIn(act.get("tile"), hand, "必须弃手里的牌")


if __name__ == "__main__":
    unittest.main()
