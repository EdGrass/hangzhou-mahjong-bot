"""补充：服务端 melds 持续为空时，按手牌长度反推副露数，不能跳回合。"""
import os
import unittest

from bot.game import play_game


HAND11 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w",
          "1t", "2t", "3t", "7t"]


class _Client:
    def __init__(self):
        self.calls = 0
        self.actions = []

    def game_state(self, gid, seq=0):
        self.calls += 1
        if self.actions:
            return {"finished": True, "snapshot": {"seat": 0, "phase": "finished",
                                                   "scores": [0, 0, 0, 0]}}
        if self.calls >= 5:
            return {"finished": True, "snapshot": {"seat": 0, "phase": "finished",
                                                   "scores": [0, 0, 0, 0]}}
        return {"seq": 10, "snapshot": {
            "seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": "7t", "my_hand": list(HAND11),
            "melds": [[], [], [], []], "last_discard": None,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False},
            "scores": [0, 0, 0, 0],
        }}

    def game_action(self, gid, action):
        self.actions.append(dict(action))
        return {}


class _Strategy:
    def decide(self, view):
        return {"action": "discard", "tile": view["my_hand"][0]}


class TestInferMeldsFromHandLength(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("HM_NO_NOTIFY")
        os.environ["HM_NO_NOTIFY"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HM_NO_NOTIFY", None)
        else:
            os.environ["HM_NO_NOTIFY"] = self._old

    def test_hand_length_infers_melds_and_discards(self):
        client = _Client()
        play_game(client, "g1", _Strategy())
        self.assertEqual(client.actions, [{"action": "discard", "tile": "1w"}],
                         "11 张摸后手牌应按长度反推 1 个副露并继续出牌")
        self.assertLessEqual(client.calls, 5)


if __name__ == "__main__":
    unittest.main()
