# -*- coding: utf-8 -*-
"""SpeedM（E+副露放宽）单测——行为与判据一致性（引擎动态验证，避免手工牌型错判）。"""
import unittest

from mahjong.shanten_exact import shanten as exact_shanten
from bot.speed import _claim_value
from bot.speedm import SpeedM, want_claim_mild
from bot.speede import SpeedE

# 3 面子 + 2b2b 对 + 5567t + 1b：碰 2b 后向听下降（E 与 M 都应接受）
PENG_IMPROVE = (["1w", "2w", "3w", "4w", "5w", "6w", "2b", "2b", "5t",
                 "5t", "6t", "7t", "1b"], "2b")
# 已听手（3 面子 + 2b2b + 5t5t + 67t 8t 结构）→ 都不接受
TENPAI = (["1w", "2w", "3w", "4w", "5w", "6w", "2b", "2b", "5t", "5t",
           "6t", "7t", "8t"], "2b")


def _rel(hand, offer):
    before = exact_shanten(hand, qidui=True, exposed_melds=0, gangs=0)
    after = _claim_value(hand, offer, "peng", 0, 0)
    return before, after


def peng_view(hand13, offer):
    return {"seat": 0, "phase": "response_peng", "turn": 1,
            "responding_seats": [0], "drawn_tile": None,
            "my_hand": list(hand13), "melds": [],
            "god": {"baotou": False, "chain_count": 0, "piao_count": 0,
                    "catch_play": False},
            "offer_tile": offer, "river": []}


class TestWantClaimMild(unittest.TestCase):
    def test_improve_case_both_accept(self):
        hand, offer = PENG_IMPROVE
        before, after = _rel(hand, offer)
        self.assertGreater(before, 0)
        self.assertLess(after, before)     # fixture 前提：碰后确实降向听
        v = peng_view(hand, offer)
        self.assertTrue(want_claim_mild(v, "peng", allow_equal=False))
        self.assertTrue(want_claim_mild(v, "peng", allow_equal=True))

    def test_tenpai_neither_accepts(self):
        hand, offer = TENPAI
        before, after = _rel(hand, offer)
        self.assertEqual(before, 0)        # fixture 前提：已听
        v = peng_view(hand, offer)
        self.assertFalse(want_claim_mild(v, "peng", allow_equal=True))

    def test_mild_equals_strict_when_improve(self):
        hand, offer = PENG_IMPROVE
        v = peng_view(hand, offer)
        self.assertEqual(SpeedM().decide(v), {"action": "peng", "tile": offer})
        self.assertEqual(SpeedE().decide(v), {"action": "peng", "tile": offer})

    def test_behavior_consistency_on_random_hands(self):
        # 随机手牌上：strict(M) 与 E 判据行为应恒一致（同判据不同入口）
        import random
        from mahjong.sim import DECK
        rng = random.Random(7)
        n_check = 0
        for _ in range(400):
            hand = sorted(rng.sample(DECK, 13))
            for offer in sorted(set(hand)):
                if hand.count(offer) < 2:
                    continue
                try:
                    before, after = _rel(hand, offer)
                except ValueError:
                    continue
                if before == 0 or after is None:
                    continue
                n_check += 1
                v = peng_view(hand, offer)
                strict_m = want_claim_mild(v, "peng", allow_equal=False)
                e = SpeedE().decide(v)
                e_want = (e or {}).get("action") == "peng"
                self.assertEqual(strict_m, e_want,
                                 "strict(M) 应与 E 判据一致: %s %s"
                                 % (hand, offer))
        self.assertGreater(n_check, 50)

    def test_no_offer_passes(self):
        v = {"seat": 0, "phase": "response_peng", "turn": 1,
             "responding_seats": [0], "drawn_tile": None,
             "my_hand": list(TENPAI[0]), "melds": [],
             "god": {"baotou": False, "chain_count": 0, "piao_count": 0,
                     "catch_play": False}, "offer_tile": None, "river": []}
        self.assertEqual(SpeedM().decide(v), {"action": "pass", "tile": ""})


if __name__ == "__main__":
    unittest.main()
