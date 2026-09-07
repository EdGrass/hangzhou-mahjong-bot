"""SpeedH 杠门控纯函数测试（不依赖 sim/真机）。"""
import unittest

from bot.speedh import bugang_value, safe_gang
from mahjong.shanten_exact import shanten as exact_shanten


def _s(hand, exposed, gangs):
    return exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                         exposed_melds=exposed, gangs=gangs)


class TestSafeGang(unittest.TestCase):
    def test_bugang_with_fourth_listening_ok(self):
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w",
                "8w", "9w", "东", "东", "东"]          # 13（含刚摸 东 已在）
        # 碰 5b 在外，手中 1 张 5b 为第 4 张；去 5b 后结构仍 ≥ 当前向听
        self.assertTrue(safe_gang(hand, drawn="东", exposed=1, gangs=0,
                                  meld_4th="5b"))

    def test_bugang_never_when_white(self):
        hand = ["白", "1w", "2w", "3w", "4w", "5w", "6w", "7w",
                "8w", "9w", "东", "东", "东"]
        self.assertFalse(safe_gang(hand, drawn="东", exposed=1, gangs=0,
                                   meld_4th="白"))

    def test_bugang_rejects_when_meld_4th_absent(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "东", "东", "东", "南"]
        self.assertFalse(safe_gang(hand, drawn="南", exposed=1, gangs=0,
                                   meld_4th="5b"))

    def test_angang_rejects_when_no_quad(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "东", "东", "东", "南"]
        self.assertFalse(safe_gang(hand, drawn="南", exposed=0, gangs=0,
                                   meld_4th=None))

    def test_angang_white_never(self):
        hand = ["白"] * 4 + ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "东"]
        self.assertFalse(safe_gang(hand, drawn="白", exposed=0, gangs=0,
                                   meld_4th=None))

    def test_angang_conservative_allows_mature_hand(self):
        # 4×7t + 已成型部分（向听低）→ 保守版允许
        hand = ["7t"] * 4 + ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "东"]
        self.assertTrue(safe_gang(hand, drawn="7t", exposed=0, gangs=0,
                                  meld_4th=None))


class TestBugangValue(unittest.TestCase):
    def test_value_positive_for_chain(self):
        self.assertGreater(bugang_value(chain=0), 0)
        self.assertGreater(bugang_value(chain=2), 0)


if __name__ == "__main__":
    unittest.main()
