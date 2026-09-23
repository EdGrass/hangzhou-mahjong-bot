# -*- coding: utf-8 -*-
"""SpeedC132 单测：非听牌段的并列必须按 **live 进张(ukeire)** 打破，且听牌段行为不变。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.shanten_exact import shanten as exact_shanten      # noqa: E402
from bot.c069routes import ukeire_counts                        # noqa: E402
from bot.speedtugc import SpeedTUGC                             # noqa: E402
from bot.speedc132 import SpeedC132                             # noqa: E402


def _view(tiles):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(tiles), "melds": [], "drawn_tile": tiles[-1],
            "offer_tile": None, "god": {"baotou": False, "chain_count": 0,
                                        "catch_play": False}, "all_melds": []}


def _sh(rem):
    return exact_shanten(list(rem), qidui=True, exposed_melds=0, gangs=0, god_meld=True)


def _ukeire(rem):
    return ukeire_counts(list(rem))[1]


# 真机窗口（offline_replay 抽到的实际一手）：基线打「北」，候选保留 6t 对子
REAL_HAND = ["5b", "7t", "5w", "1b", "6t", "2b", "西", "3w", "9b",
             "6w", "4w", "8b", "北", "6t"]
# 已听牌的一手（s=0），本候选设计上不动它
TENPAI_HAND = ["1w", "2w", "3w", "4b", "5b", "6b", "1t", "2t", "3t",
               "7w", "8w", "9w", "东", "东"]


class TestSpeedC132(unittest.TestCase):
    def test_registered(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc132", F)
        self.assertIsInstance(F["speedc132"](), SpeedC132)

    def test_only_difference_is_the_discard_hook(self):
        self.assertIs(SpeedC132.decide, SpeedTUGC.decide)
        self.assertTrue(SpeedTUGC.GOD_MELD and SpeedC132.GOD_MELD)

    def test_candidate_reaches_best_ukeire_in_min_shanten_group(self):
        hand = list(REAL_HAND)
        best, smin = None, None
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            s = _sh(rem)
            smin = s if smin is None else min(smin, s)
            best = max(best or 0, 0)
        # 最小向听组内最优进张
        top, best_u = None, None
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            if _sh(rem) != smin:
                continue
            u = _ukeire(rem)
            if best_u is None or u > best_u:
                best_u, top = u, d
        act = SpeedC132().decide(_view(hand))
        rem = list(hand)
        rem.remove(act["tile"])
        self.assertEqual(_sh(rem), smin)
        self.assertEqual(_ukeire(rem), best_u)

    def test_baseline_leaves_ukeire_on_the_table(self):
        """回归意义：基线在同一手上达不到最优进张（这正是本候选要修掉的缺陷）。"""
        hand = list(REAL_HAND)
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            cands.append((d, _sh(rem), _ukeire(rem)))
        smin = min(c[1] for c in cands)
        best_u = max(c[2] for c in cands if c[1] == smin)
        act = SpeedTUGC().decide(_view(hand))
        rem = list(hand)
        rem.remove(act["tile"])
        self.assertEqual(_sh(rem), smin)            # 基线确实最小向听
        self.assertLess(_ukeire(rem), best_u)       # 但进张不是最优

    def test_tenpai_behaviour_unchanged(self):
        a = SpeedTUGC().decide(_view(list(TENPAI_HAND)))
        b = SpeedC132().decide(_view(list(TENPAI_HAND)))
        self.assertEqual(a["tile"], b["tile"])


if __name__ == "__main__":
    unittest.main()
