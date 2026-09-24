# -*- coding: utf-8 -*-
"""c185：**真版 true 候选**（c156 + YouCaiBiKao 闸门 + 转爆头）单测。

锁三件事：
① 闸门语义与 c169~c172/c176/c184 一致（平胡被拦、爆头/链条放行）；
② **单变量纪律**：非"该胡却被拦"的场合，c185 与 c156 **逐条相同**（闸门必须惰性）；
③ 已注册（run_bot 工厂 + rules_guard 静态兜底），漏注册会让月底切换静默跑到别处。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc151 import SpeedC151
from bot.speedc156 import SpeedC156
from bot.speedc185 import SpeedC185

PLAIN = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
         "东", "东", "东", "南", "南"]
PLAIN_DRAWN = "南"
BAOTOU = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白", "5b"]


def _view(hand, drawn, chain=0, piao=0):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": chain, "catch_play": False,
                    "piao_count": piao, "god_discarder_seat": -1}}


# 明显未听牌的手牌：闸门在这些局面上必须完全惰性
NO_HU_HANDS = [
    (["1w", "3w", "5w", "7w", "9w", "1b", "4b", "7b", "2t", "5t", "8t", "东", "西", "北"], "北"),
    (["2w", "2w", "5w", "8w", "1b", "1b", "3b", "6b", "9b", "3t", "6t", "南", "中", "发"], "发"),
    (["1w", "4w", "7w", "2b", "5b", "8b", "3t", "6t", "9t", "东", "南", "西", "北", "白"], "白"),
]


class TestSpeedC185(unittest.TestCase):
    def test_flags(self):
        p = SpeedC185()
        self.assertFalse(p.GOD_MELD)              # FastYCBKMixin：白不当万能面子
        self.assertTrue(p.YOU_CAI_BI_KAO)
        self.assertTrue(p.FORCE_BAOTOU_ON_BLOCK)
        self.assertTrue(p.SELF_GANG)              # C146 继承（暗杠/补杠开关）

    def test_plain_joker_hu_blocked(self):
        act = SpeedC185().decide(_view(PLAIN, PLAIN_DRAWN)) or {}
        self.assertEqual(act.get("action"), "discard")

    def test_baotou_allowed(self):
        act = SpeedC185().decide(_view(BAOTOU, "5b")) or {}
        self.assertEqual(act.get("action"), "hu")

    def test_chain_allowed(self):
        act = SpeedC185().decide(_view(PLAIN, PLAIN_DRAWN, chain=1)) or {}
        self.assertEqual(act.get("action"), "hu")

    def test_hooks_are_true_route(self):
        # 出牌走 c151 的路线键；副露走 c156 的学习门控 —— 三者都必须还在链上
        self.assertIs(SpeedC185._pick_discard, SpeedC151._pick_discard)
        self.assertIs(SpeedC185._want_claim, SpeedC156._want_claim)

    def test_gate_is_inert_when_no_hu(self):
        """**单变量纪律**：c156 不胡 ⇒ c185 必须给出完全相同的动作。"""
        base, cand = SpeedC156(), SpeedC185()
        for hand, drawn in NO_HU_HANDS:
            v = _view(hand, drawn)
            a = base.decide(v) or {}
            b = cand.decide(v) or {}
            self.assertNotEqual(a.get("action"), "hu", "夹具失效：该局面不该胡 %s" % hand)
            self.assertEqual(a, b, "闸门不该在非胡局面改变动作：%s" % hand)

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            self.assertIn("speedc185", fh.read())
        from tools import rules_guard
        self.assertIn("speedc185", rules_guard.NEEDS_YCBK)


if __name__ == "__main__":
    unittest.main()
