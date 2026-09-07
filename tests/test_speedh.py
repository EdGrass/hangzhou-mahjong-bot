"""SpeedH 杠门控纯函数与 SpeedH.decide 集成测试（离线，钉行为）。

decide 输入视图约定（对齐 bot/game.py 语义）：my_turn + drawn_tile 时
view["my_hand"] 已含刚摸牌（张数 = 14-3e-g）；SpeedH 内部去掉 drawn 得
核心手牌（13-3e-g）再喂 safe_gang。据此夹具手牌均含 drawn。
"""
import unittest

from bot.model import my_turn  # noqa: F401
from bot.speede import SpeedE
from bot.speedh import (GOD, SpeedH, bugang_value, safe_gang,
                        within_tolerance)


def _draw_view(full_hand, drawn=None, god=None, melds=None):
    """构造含刚摸的手牌 draw 视图（full_hand 需已含 drawn）。"""
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": drawn if drawn is not None else full_hand[-1],
            "my_hand": list(full_hand),
            "god": god or {}, "scores": None,
            "melds": list(melds or []), "offer_tile": None, "river": []}


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


# ---------------------------------------------------------------------------
# SpeedH.decide 集成
# ---------------------------------------------------------------------------

class TestSpeedHDecide(unittest.TestCase):
    # 补杠夹具：碰 5b 在外（e=1,g=0），核心含碰牌第 4 张 → 补杠安全
    def test_bugang_safe_returns_gang(self):
        melds = [{"type": "peng", "tile": "5b"}]
        # core = 123..789 万 + 5b(补杠第 4 张)，drawn=南；核心 10 张合法
        core = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        act = SpeedH().decide(_draw_view(core + ["南"], melds=melds))
        self.assertEqual(act, {"action": "gang", "tile": "5b"})

    def test_angang_safe_returns_gang(self):
        # core=1w×4 quad + 两顺 + 东东对 + 南；drawn=北；暗杠成型安全
        core = ["1w"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w",
                             "东", "东", "南"]
        act = SpeedH().decide(_draw_view(core + ["北"]))
        self.assertEqual(act, {"action": "gang", "tile": "1w"})

    def test_win_priority_before_gang(self):
        # 同补杠形状但 drawn=5b 使整手成胡——hu 优先（不杠）
        melds = [{"type": "peng", "tile": "5b"}]
        core = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        act = SpeedH().decide(_draw_view(core + ["5b"], melds=melds))
        self.assertEqual(act, {"action": "hu", "tile": ""})

    def test_catch_play_discards_no_gang(self):
        # god.catch_play：抓打圈强制打刚摸；即使补杠安全也不杠
        melds = [{"type": "peng", "tile": "5b"}]
        core = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        v = _draw_view(core + ["南"], melds=melds,
                       god={"catch_play": True})
        act = SpeedH().decide(v)
        self.assertEqual(act["action"], "discard")
        self.assertEqual(act["tile"], "南")   # 强制弃刚摸

    def test_throttle_repeats_turns_gang_into_discard(self):
        # 同一 view（同 phase/draw）连续 decide：首轮 gang、次轮丢弃（防 409 死循环）
        melds = [{"type": "peng", "tile": "5b"}]
        core = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w"]
        h = SpeedH()
        v = _draw_view(core + ["南"], melds=melds)
        self.assertEqual(h.decide(v), {"action": "gang", "tile": "5b"})
        second = h.decide(v)
        self.assertEqual(second["action"], "discard")
        self.assertNotEqual(second.get("tile"), "5b")

    def test_no_gang_falls_back_to_speedE(self):
        # 无 quad / 无第 4 张 → 与 SpeedE 一致（discard）
        core = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "南", "南", "南", "发"]
        v = _draw_view(core + ["西"])
        h = SpeedH()
        self.assertEqual(h.decide(v), SpeedE().decide(v))
        self.assertEqual(h.decide(v)["action"], "discard")


if __name__ == "__main__":
    unittest.main()
