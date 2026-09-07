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
        # 注：旧例 4w 连顺 123..9w+東東 恰为自摸胡形——修复后 hu 优先守卫会先
        # 交还 SpeedE(→hu) 而非 gang；改用【非胡形】的 1w×4 钉暗杠-探针语义：
        # 其余 10 张全为互不重复散牌（无对子/无法成面），is_win=False。
        hand = ["1w"] * 4 + ["8b", "9b", "1t", "2t", "东", "南", "中", "发",
                "3w", "5w"]
        act = ProbeGang().decide(_view(hand, drawn="1w", can_gang=True))
        self.assertEqual(act, {"action": "gang", "tile": "1w"})

    def test_gang_without_can_gang_key(self):
        # 真机 snap_view 从不产出 can_gang 键 → view 不含该键时仍须直接上杠：
        # 探针不以客户端预测为门，交由服务器裁决（409 也是观测信号）。
        hand = ["1w"] * 4 + ["8b", "9b", "1t", "2t", "东", "南", "中", "发",
                "3w", "5w"]
        v = _view(hand, drawn="1w")          # _view 默认 can_gang=True
        v.pop("can_gang", None)               # 移除，模拟真机视图（无此键）
        self.assertNotIn("can_gang", v)
        act = ProbeGang().decide(v)
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

    def test_window_peng_when_pair_offer(self):
        # 窗口 phase=response_peng：手牌对 offer 满 2（非白）→ 无条件碰，制造补杠机会。
        hand = ["5b"] * 2 + ["1w", "2w", "3w", "4w", "6w", "7w", "8w", "9w",
                "南", "北", "中", "发"]
        act = ProbeGang().decide({
            "seat": 0, "phase": "response_peng", "turn": 1,
            "responding_seats": [0], "offer_tile": "5b",
            "my_hand": hand, "god": {}, "scores": None,
            "melds": [], "river": []})
        self.assertEqual(act, {"action": "peng", "tile": "5b"})

    def test_window_white_offer_always_pass(self):
        # offer 为白 → 一律 pass（白板弃出无人可吃碰杠）
        act = ProbeGang().decide({
            "seat": 0, "phase": "response_peng", "turn": 1,
            "responding_seats": [0], "offer_tile": "白",
            "my_hand": ["白"] * 3 + ["1w", "2w", "3w", "4w", "5w",
                                     "9b", "东", "东", "北", "中", "发"],
            "god": {}, "scores": None, "melds": [], "river": []})
        self.assertEqual(act, {"action": "pass", "tile": ""})


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
