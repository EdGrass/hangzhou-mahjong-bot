# -*- coding: utf-8 -*-
"""C122 单测：副露门控 relax vs strict 的行为差异（单变量可测）。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc122 import C122Policy, want_claim_relaxed   # noqa: E402
from bot.speedtugc import want_claim_strict_meld           # noqa: E402

# 由穷举搜出：向听不恶化(after==before)的碰/明杠窗口。
# 这是 speedc122 与 speedc073w4 唯一的判据差异所在。
_HAND = ["4w", "4w", "4w", "5w", "6b", "6w", "7b", "8t", "8w", "9t", "东", "东", "东"]
_OFFER = "东"


def _view(hand, offer, phase="response_peng", melds=()):
    return {"seat": 0, "phase": phase, "offer_tile": offer,
            "my_hand": list(hand), "melds": list(melds),
            "drawn_tile": None, "god": {},
            "responding_seats": [0], "actor_seat": 1}


class TestC122(unittest.TestCase):
    def test_loads_with_production_model(self):
        p = C122Policy(model_path=os.path.join(ROOT, "var", "c073_orig_w4_net.pt"))
        self.assertEqual(p.name, "speedc122")
        self.assertEqual(p.shanten_range, (0, 2))

    def test_relaxed_accepts_equal_shanten_claim_that_strict_rejects(self):
        v = _view(_HAND, _OFFER)
        self.assertTrue(want_claim_relaxed(v, "peng"),
                        "relaxed 应收下「向听不恶化」的碰")
        self.assertFalse(want_claim_strict_meld(v, "peng"),
                         "strict 应拒掉「向听未严格下降」的碰")

    def test_decide_claims_where_strict_would_pass(self):
        """已知风险（记录在案，不掩盖）：拆三张组的同向听副露会被 relaxed 收下。"""
        p = C122Policy(model_path=os.path.join(ROOT, "var", "c073_orig_w4_net.pt"))
        act = p.decide(_view(_HAND, _OFFER))
        self.assertIn(act.get("action"), ("peng", "gang"),
                      "relaxed 门控下应发起副露，而不是 pass")
        self.assertEqual(act.get("tile"), _OFFER)


if __name__ == "__main__":
    unittest.main()
