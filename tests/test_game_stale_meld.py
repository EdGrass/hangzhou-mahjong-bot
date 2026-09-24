"""副露后服务端 melds 暂未更新时，不能让出牌回合被跳过。

场景：我们刚碰成功，服务端快照 my_hand 已是碰后 11 张，但 melds 仍为空。
MeldTracker 已记录 1 组碰，长度与 11 张完全一致；此时应采用本地副露计数继续出牌。
"""
import os
import unittest

from bot.game import play_game


HAND13 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w",
          "5b", "5b", "1t", "2t", "3t", "4t"]
HAND11 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w",
          "1t", "2t", "3t", "7t"]


def _snap(seq, phase, turn, hand, drawn=None, last=None, responding=None):
    return {
        "seq": seq, "seat": 0, "phase": phase, "turn": turn,
        "responding_seats": list(responding or []),
        "drawn_tile": drawn, "my_hand": list(hand),
        "melds": [[], [], [], []],
        "last_discard": last,
        "god": {"baotou": False, "chain_count": 0, "catch_play": False},
        "scores": [0, 0, 0, 0],
    }


class _Client:
    def __init__(self):
        self.state_calls = []
        self.actions = []
        self.peng_done = False

    def game_state(self, gid, seq=0):
        self.state_calls.append(seq)
        if not self.actions:
            return {"seq": 1, "snapshot": _snap(
                1, "response_peng", 1, HAND13, last="5b", responding=[0])}
        if self.actions[-1].get("action") == "peng":
            return {"seq": 2, "snapshot": _snap(
                2, "draw", 0, HAND11, drawn="7t")}
        return {"finished": True, "snapshot": {"seat": 0, "phase": "finished",
                                               "scores": [0, 0, 0, 0]}}

    def game_action(self, gid, action):
        self.actions.append(dict(action))
        return {}


class _Strategy:
    def __init__(self):
        self.views = []

    def decide(self, view):
        self.views.append(view)
        if view.get("phase") == "response_peng" and view.get("offer_tile") == "5b":
            return {"action": "peng", "tile": "5b"}
        if view.get("phase") == "draw" and view.get("turn") == view.get("seat"):
            return {"action": "discard", "tile": view["my_hand"][0]}
        return {"action": "pass", "tile": ""}


class TestStaleMeldFallback(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("HM_NO_NOTIFY")
        os.environ["HM_NO_NOTIFY"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HM_NO_NOTIFY", None)
        else:
            os.environ["HM_NO_NOTIFY"] = self._old

    def test_hand_matching_tracker_melds_can_discard(self):
        client = _Client()
        strategy = _Strategy()
        play_game(client, "g1", strategy)

        self.assertEqual(
            client.actions,
            [{"action": "peng", "tile": "5b"}, {"action": "discard", "tile": "1w"}],
            "服务端 melds 暂空但手牌长度与本地碰组一致时，必须继续出牌",
        )


if __name__ == "__main__":
    unittest.main()
