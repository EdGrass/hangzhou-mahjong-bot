"""示例策略（NaiveStrategy）与单局结束判定的单测。"""
import unittest

from bot.game import _end_reason
from bot.model import snap_view
from bot.strategy import NaiveStrategy


def _view(**kw):
    snap = {"seat": 0, "phase": "deal", "turn": -1, "responding_seats": [],
            "drawn_tile": None, "my_hand": [], "god": {}}
    snap.update(kw)
    return snap_view(snap)


class TestNaiveStrategy(unittest.TestCase):
    def setUp(self):
        self.s = NaiveStrategy()

    def test_draw_discard_first(self):
        act = self.s.decide(_view(phase="draw", turn=0,
                                  my_hand=["7t", "1w", "白"]))
        self.assertEqual(act, {"action": "discard", "tile": "7t"})

    def test_catch_play_discard_drawn_only(self):
        # 抓打圈：即使手牌首张不是刚摸的，也只能出刚摸的牌
        act = self.s.decide(_view(phase="draw", turn=0, my_hand=["1w", "5b"],
                                  drawn_tile="5b",
                                  god={"catch_play": True}))
        self.assertEqual(act, {"action": "discard", "tile": "5b"})

    def test_draw_no_hand_no_action(self):
        self.assertIsNone(self.s.decide(_view(phase="draw", turn=0, my_hand=[])))

    def test_window_pass_when_member(self):
        act = self.s.decide(_view(phase="response_peng", turn=1,
                                  responding_seats=[0, 2], my_hand=["1w", "1w", "2w"],
                                  drawn_tile="1w"))
        self.assertEqual(act, {"action": "pass", "tile": ""})

    def test_window_not_member_no_action(self):
        self.assertIsNone(self.s.decide(
            _view(phase="response_chi", turn=1, responding_seats=[2])))

    def test_deal_no_action(self):
        self.assertIsNone(self.s.decide(_view(phase="deal")))

    def test_never_submits_hu_or_chi(self):
        # 骨架期示例：不主动胡、不吃不碰不杠 —— 只出牌或过
        act = self.s.decide(_view(phase="draw", turn=0, my_hand=["1w"],
                                  drawn_tile="9b"))
        self.assertNotIn(act["action"], ("hu", "chi", "peng", "gang"))


class TestEndReason(unittest.TestCase):
    def test_finished_flag(self):
        self.assertIsNotNone(_end_reason({"finished": True}, None))

    def test_phase_finished(self):
        self.assertIsNotNone(_end_reason({}, {"phase": "finished"}))

    def test_running_ok(self):
        self.assertIsNone(_end_reason({}, {"phase": "draw"}))
        self.assertIsNone(_end_reason({"pending": True}, None))


if __name__ == "__main__":
    unittest.main()
