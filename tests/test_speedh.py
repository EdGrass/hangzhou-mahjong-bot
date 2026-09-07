"""SpeedH 杠门控纯函数测试（不依赖 sim/真机）。"""
import unittest

from bot.speedh import GOD, bugang_value, safe_gang, within_tolerance


class TestWithinTolerance(unittest.TestCase):
    def test_window_boundary(self):
        self.assertTrue(within_tolerance(0, 2, 2))     # 恰好容忍上界
        self.assertFalse(within_tolerance(0, 3, 2))    # 超容忍
        self.assertTrue(within_tolerance(3, 0, 2))     # 杠后更好也允许
        self.assertFalse(within_tolerance(None, 1, 2))  # 异常值不安全
        self.assertFalse(within_tolerance(0, None, 2))


class TestSafeGangBugang(unittest.TestCase):
    # 碰 5b 在外（e=1,g=0）→ 核心手牌须 13-3=10 张
    def test_bugang_with_fourth_listening_ok(self):
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        self.assertTrue(safe_gang(hand, exposed=1, gangs=0, meld_4th="5b"))

    def test_bugang_never_when_white(self):
        hand = ["白", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        self.assertFalse(safe_gang(hand, exposed=1, gangs=0, meld_4th="白"))

    def test_bugang_rejects_when_fourth_absent(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "南"]
        self.assertFalse(safe_gang(hand, exposed=1, gangs=0, meld_4th="5b"))

    def test_bugang_rejects_wrong_length(self):
        # 长度 11 ≠ 13-3*1-0=10 → 不杠（不裁牌）
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w",
                "8w", "9w", "南"]
        self.assertFalse(safe_gang(hand, exposed=1, gangs=0, meld_4th="5b"))


class TestSafeGangAngang(unittest.TestCase):
    # e=0,g=0 → 核心 13 张
    def test_angang_rejects_no_quad(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w",
                "9w", "东", "东", "东", "南"]
        self.assertFalse(safe_gang(hand, exposed=0, gangs=0, meld_4th=None))

    def test_angang_white_never(self):
        hand = ["白"] * 4 + ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        self.assertFalse(safe_gang(hand, exposed=0, gangs=0, meld_4th=None))

    def test_angang_allows_mature_quad(self):
        # 1w×4 已自成杠组 + 另两面子 + 一对 → 杠后不劣化
        hand = ["1w"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w", "东", "东", "南"]
        self.assertTrue(safe_gang(hand, exposed=0, gangs=0, meld_4th=None))

    def test_angang_rejects_raw_discard_hand(self):
        # 实测（shanten_exact）：杠前 0 向听、暗杠后 1 向听 → 差值 1 ∈ [0,tol=2]，在容忍内
        # 故 safe_gang=True；该散手杠后并不劣化 → 断言取 assertTrue（不要删用例）。
        hand = ["1w"] * 4 + ["9w", "8w", "7w", "6w", "5w", "4w", "3w", "2w", "东"]
        self.assertTrue(safe_gang(hand, exposed=0, gangs=0, meld_4th=None))


class TestBugangValue(unittest.TestCase):
    def test_doubles_per_chain(self):
        self.assertEqual(bugang_value(0), 1.0)
        self.assertEqual(bugang_value(1), 2.0)
        self.assertEqual(bugang_value(2), 4.0)


if __name__ == "__main__":
    unittest.main()
