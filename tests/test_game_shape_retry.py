"""play_game 手牌形态不一致时的恢复测试。

场景：服务端瞬时快照仍是副露/自杠前的旧 11 张手牌，但已经给出刚摸牌。
期望：客户端立即拉 seq=0 全量快照，而不是继续用旧 seq 挂长轮询，
否则该出牌回合会被服务端超时代打。
"""
import os
import unittest

from bot.game import play_game


SNAP_INCONSISTENT = {
    "seat": 0, "phase": "draw", "turn": 0,
    "responding_seats": [], "drawn_tile": "6w",
    "my_hand": ["3t", "3w", "4t", "4w", "6w"],
    "melds": [[], [], [], []],
    "last_discard": None,
    "god": {"baotou": False, "chain_count": 0, "catch_play": False},
    "scores": [0, 0, 0, 0],
}

SNAP_CONSISTENT = dict(SNAP_INCONSISTENT)
SNAP_CONSISTENT["my_hand"] = [
    "3t", "3w", "4t", "4w", "5t", "7t", "7w", "8b", "8b", "白",
    "1b", "2b", "5b", "9b",
]


class _Client:
    def __init__(self):
        self.state_calls = []
        self.actions = []

    def game_state(self, gid, seq=0):
        self.state_calls.append(seq)
        if self.actions:
            return {"finished": True, "snapshot": {"seat": 0, "phase": "finished",
                                                       "scores": [0, 0, 0, 0]}}
        if len(self.state_calls) == 1:
            return {"seq": 7, "snapshot": SNAP_INCONSISTENT}
        if seq == 0:
            return {"seq": 8, "snapshot": SNAP_CONSISTENT}
        return {"pending": True}

    def game_action(self, gid, action):
        self.actions.append(action)
        return {}


class _Strategy:
    def __init__(self):
        self.views = []

    def decide(self, view):
        self.views.append(view)
        return {"action": "discard", "tile": "1b"}


class TestShapeMismatchRecovery(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("HM_NO_NOTIFY")
        os.environ["HM_NO_NOTIFY"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HM_NO_NOTIFY", None)
        else:
            os.environ["HM_NO_NOTIFY"] = self._old

    def test_shape_mismatch_forces_full_snapshot(self):
        client = _Client()
        strategy = _Strategy()
        play_game(client, "g1", strategy)

        self.assertGreaterEqual(len(client.state_calls), 2)
        self.assertEqual(
            client.state_calls[1], 0,
            "形态不一致后应立即 seq=0 全量重建，不能继续用旧 seq 等长轮询",
        )
        self.assertEqual(client.actions, [{"action": "discard", "tile": "1b"}])


if __name__ == "__main__":
    unittest.main()
