# -*- coding: utf-8 -*-
"""SpeedC148 单测：**有财必拷响（YouCaiBiKao）保险臂**。

规则（指南 §1.6）：手上有财神时**不允许平胡**，必须爆头/杠开（链）——七对不是平胡，应放行。
本臂 = C146（明杠+自杠+吃碰+财飘）+ `GOD_MELD=False`（白留作万能听）+ 胡牌合法性闸门。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc146 import SpeedC146        # noqa: E402
from bot.speedc148 import SpeedC148        # noqa: E402
from bot.speedt import _best_discard_t     # noqa: E402
from bot.speedtugc import SpeedTUGC        # noqa: E402

# ① 平胡 + 手上有白（白当面子里的 3w）⇒ 本规则下**不许胡**
PLAIN_HAND = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b",
              "东", "东", "东", "南", "南"]
PLAIN_DRAWN = "南"
# ② 爆头 + 白（摸牌前 4 面子 + 白孤）⇒ 允许
BAOTOU_PRE = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白"]
BAOTOU_HAND = BAOTOU_PRE + ["5b"]
# ③ 七对 + 白当对子的一半（摸牌前 6 对 + 孤张）⇒ 不是平胡，允许
QIDUI_PRE = ["白", "1w", "2w", "2w", "3b", "3b", "4b", "4b", "5t", "5t", "6t", "6t", "中"]
QIDUI_HAND = QIDUI_PRE + ["中"]
# ④ GOD_MELD 会改变弃牌的真机盘
GM_HAND = ["1b", "1b", "1w", "2w", "3w", "7b", "7b", "7b", "8b", "8b", "8w", "9w", "9w", "白"]
GM_DRAWN = "9w"


def _view(hand, drawn, chain=0, piao=0, melds=None):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": list(melds or []), "drawn_tile": drawn,
            "offer_tile": None, "river": [], "river_len": 6, "all_melds": [],
            "can_gang": True,
            "god": {"baotou": False, "chain_count": chain, "catch_play": False,
                    "piao_count": piao, "god_discarder_seat": -1}}


class TestSpeedC148(unittest.TestCase):
    def test_registered_and_flags(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc148", F)
        s = SpeedC148()
        self.assertIsInstance(s, SpeedC146)
        self.assertFalse(s.GOD_MELD)
        self.assertTrue(s.YOU_CAI_BI_KAO)
        self.assertEqual(SpeedC146.GOD_MELD, True)   # 基线不受影响

    def test_plain_win_with_joker_is_blocked(self):
        v1 = _view(PLAIN_HAND, PLAIN_DRAWN)
        v2 = _view(PLAIN_HAND, PLAIN_DRAWN)
        self.assertEqual((SpeedC146().decide(v1) or {}).get("action"), "hu")
        act = SpeedC148().decide(v2)
        self.assertEqual(act.get("action"), "discard")      # 改为出牌，不白交一个被拒的 hu

    def test_baotou_win_with_joker_allowed(self):
        v = _view(BAOTOU_HAND, "5b")
        self.assertIsNotNone(SpeedC148()._ycbk_violation(v, BAOTOU_PRE, 0, 0))
        v2 = _view(BAOTOU_HAND, "5b")
        self.assertFalse(SpeedC148()._ycbk_violation(v2, BAOTOU_PRE, 0, 0))
        v3 = _view(BAOTOU_HAND, "5b")
        self.assertEqual((SpeedC148().decide(v3) or {}).get("action"), "hu")

    def test_chain_win_with_joker_allowed(self):
        """杠开/财飘（chain_count>0）⇒ 允许胡（哪怕手牌是平胡形）。"""
        v = _view(PLAIN_HAND, PLAIN_DRAWN, chain=1)
        self.assertFalse(SpeedC148()._ycbk_violation(v, PLAIN_HAND[:-1] + ["南"], 0, 0))
        v2 = _view(PLAIN_HAND, PLAIN_DRAWN, chain=1)
        self.assertEqual((SpeedC148().decide(v2) or {}).get("action"), "hu")

    def test_qidui_win_with_joker_allowed(self):
        """七对不是平胡 ⇒ 闸门放行（不按"平胡"拦）。

        注：这一盘基线会因为 C036 弃胡逻辑主动**弃 1w 换爆头七对**（fan 2→4，0.71×4>2），
        所以这里不该断言 action==hu；正确断言是"闸门不拦"且 c148 的行为与 c146 一致。
        """
        v = _view(QIDUI_HAND, "中")
        self.assertFalse(SpeedC148()._ycbk_violation(v, QIDUI_PRE, 0, 0))
        self.assertEqual(SpeedC148().decide(_view(QIDUI_HAND, "中")),
                         SpeedC146().decide(_view(QIDUI_HAND, "中")))

    def test_god_meld_false_changes_discard(self):
        """GOD_MELD=False 真的生效：真机盘 True→8w、False→1w。"""
        self.assertEqual(_best_discard_t(list(GM_HAND), GM_DRAWN, 0, 0, god_meld=True), "8w")
        self.assertEqual(_best_discard_t(list(GM_HAND), GM_DRAWN, 0, 0, god_meld=False), "1w")
        self.assertEqual(SpeedC148()._pick_discard(list(GM_HAND), GM_DRAWN, 0, 0),
                         _best_discard_t(list(GM_HAND), GM_DRAWN, 0, 0, god_meld=False))


if __name__ == "__main__":
    unittest.main()
