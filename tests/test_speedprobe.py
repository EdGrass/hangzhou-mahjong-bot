"""speedprobe 探针策略语义测试（离线，钉行为）."""
import unittest

from bot.model import my_turn  # noqa: F401
from bot.speedprobe import ProbeGang, ProbeHuPass
from bot.speede import SpeedE


def _view(hand, drawn, god=None, melds=None, can_gang=True):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": drawn, "my_hand": list(hand),
            "god": god or {}, "scores": None,
            "melds": list(melds or []), "offer_tile": None,
            "can_gang": can_gang, "river": []}


class TestProbeGang(unittest.TestCase):
    def test_angang_when_quad_in_hand(self):
        hand = ["1w"] * 4 + ["2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东"]
        act = ProbeGang().decide(_view(hand, drawn="1w", can_gang=True))
        self.assertEqual(act, {"action": "gang", "tile": "1w"})

    def test_white_never_gang(self):
        # 注：白×4 的 14 张若用连顺 123.. 会直接成胡，回退 SpeedE 即 hu，
        # 无法体现"白板不发杠→正常弃牌"。改为散张 4 白（非胡形）以钉这里程碑行为。
        hand = ["白"] * 4 + ["1w", "9w", "1b", "9b", "1t", "9t", "东", "南",
                "西", "北"]
        act = ProbeGang().decide(_view(hand, drawn="白", can_gang=True))
        self.assertEqual(act["action"], "discard")

    def test_bugang_when_peng_plus_fourth(self):
        melds = [{"type": "peng", "tile": "5b", "tiles": ["5b"] * 3}]
        hand = ["5b", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "东"]
        act = ProbeGang().decide(_view(hand, drawn="5b", melds=melds))
        self.assertEqual(act, {"action": "gang", "tile": "5b"})


class TestProbeHuPass(unittest.TestCase):
    def test_hu_pass_discards_instead_of_hu(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        act = ProbeHuPass().decide(_view(hand, drawn="东"))
        self.assertEqual(act["action"], "discard")


class TestProbeFallsBackToSpeedE(unittest.TestCase):
    def test_no_gang_situation_plays_speedE(self):
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        p = ProbeGang()
        e = SpeedE()
        v = _view(hand, drawn="南")
        self.assertEqual(p.decide(v)["tile"], e.decide(v)["tile"])


if __name__ == "__main__":
    unittest.main()
