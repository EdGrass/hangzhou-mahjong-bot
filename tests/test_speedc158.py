# -*- coding: utf-8 -*-
"""speedc158（副露侧大束 = c156 学习补加 + 末盘放宽）单测。

夹具 1（末盘）：真机窗口 kind=chi offer=3t river_len=48，**同向听(1) 且等张不变(14→14)** ⇒
  质量门控拒（因为它只在"等张变多"时才补），末盘放宽应当接受。
夹具 2/3：沿用 c156 的学习补加夹具（碰 9t / 吃 4w）。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import SpeedC151                      # noqa: E402
from bot.speedc156 import SpeedC156                      # noqa: E402
from bot.speedc158 import SpeedC158                      # noqa: E402

LATE = dict(
    kind="chi", offer="3t",
    hand=["2w", "6t", "6w", "1b", "1b", "3t", "4w", "6t", "8t", "5t", "7w", "7t", "4t"],
    melds=[], river_len=48,
    river=["1t","1t","北","东","南","南","东","6b","西","东","东","1w","3w","发","发","6b","西","6w",
           "2t","9w","西","1w","8b","7b","9b","2t","2t","6b","9w","南","发","4b","6w","9w","1b","2b",
           "3w","2w","2w","2b","中","1b","7w","中","2t","4w","4w","5b"])
PENG = dict(kind="peng", offer="9t", river_len=8,
            hand=["8t", "西", "1t", "9b", "9t", "9w", "9t", "东", "5b", "西", "东", "2w", "8t"],
            melds=[], river=["5w", "东", "中", "2t", "1t"])
CHI = dict(kind="chi", offer="4w", river_len=10,
           hand=["6w", "2t", "白", "1b", "6t", "5t", "2w", "7w", "白", "5w", "3w", "1w", "2b"],
           melds=[], river=["中", "北", "西", "南", "发", "9t", "4w"])


def _view(spec):
    return {"seat": 0, "phase": "response_peng" if spec["kind"] == "peng" else "response_chi",
            "turn": 0, "my_hand": list(spec["hand"]), "melds": list(spec["melds"]),
            "offer_tile": spec["offer"], "river": list(spec["river"]),
            "river_len": spec["river_len"], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC158LateAndLearned(unittest.TestCase):
    def test_late_fixture_is_discriminating(self):
        self.assertFalse(SpeedC151()._want_claim(_view(LATE), "chi", None),
                         "夹具前提：质量门控在【同向听 + 等张不变】时必须拒绝")
        self.assertTrue(SpeedC158()._want_claim(_view(LATE), "chi", None),
                        "末盘（河牌 48）且等张退化 0 ⇒ 应当接受")

    def test_late_rule_needs_late_river(self):
        v = _view(LATE)
        v["river_len"] = 20
        v["river"] = v["river"][:20]
        self.assertFalse(SpeedC158()._want_claim(v, "chi", None),
                         "早盘不得放宽（河牌 20 < 40）")

    def test_learned_adds_still_work(self):
        pol = SpeedC158()
        self.assertTrue(pol._want_claim(_view(PENG), "peng", None))
        self.assertTrue(pol._want_claim(_view(CHI), "chi", None))

    def test_never_vetoes_base(self):
        pol = SpeedC158()
        import bot.speedc151 as s151
        orig = s151.SpeedC151._want_claim
        try:
            s151.SpeedC151._want_claim = lambda self, v, k, p=None: True
            self.assertTrue(pol._want_claim(_view(LATE), "chi", None))
        finally:
            s151.SpeedC151._want_claim = orig

    def test_source_guardrails(self):
        src = inspect.getsource(SpeedC158)
        self.assertIn("super()._want_claim(", src)
        self.assertIn("RIVER_LATE", src)
        self.assertIn("UKEIRE_TOL", src)
