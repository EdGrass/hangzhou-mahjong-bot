"""跨局相同弃牌窗口不能被上一局去重键吞掉。"""
import os
import unittest

from bot.game import play_game


def _snap(seq, phase="response_peng", turn=1, offer="5b"):
    return {
        "seq": seq, "seat": 0, "phase": phase, "turn": turn,
        "responding_seats": [0], "drawn_tile": None,
        "my_hand": ["1w", "2w", "3w", "4w", "5w", "6w", "7w",
                    "8w", "9w", "1b", "2b", "3b", "4b"],
        "melds": [[], [], [], []],
        "last_discard": offer,
        "god": {"baotou": False, "chain_count": 0, "catch_play": False},
        "scores": [0, 0, 0, 0],
    }


class _Client:
    def __init__(self):
        self.state_calls = []
        self.actions = []

    def game_state(self, gid, seq=0):
        self.state_calls.append(seq)
        n = len(self.state_calls)
        if n == 1:
            return {"seq": 1, "snapshot": _snap(1)}
        if n == 2:
            return {"seq": 2, "events": [
                {"seq": 2, "type": "round_ended", "data": {"scores": [0, 0, 0, 0]}}
            ]}
        if n == 3:
            return {"seq": 3, "snapshot": _snap(3)}
        return {"finished": True, "snapshot": {"seat": 0, "phase": "finished",
                                               "scores": [0, 0, 0, 0]}}

    def game_action(self, gid, action):
        self.actions.append(action)
        return {}


class _Strategy:
    def __init__(self):
        self.calls = 0

    def decide(self, view):
        self.calls += 1
        return {"action": "pass", "tile": ""}


class TestWindowResetAcrossRound(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("HM_NO_NOTIFY")
        os.environ["HM_NO_NOTIFY"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HM_NO_NOTIFY", None)
        else:
            os.environ["HM_NO_NOTIFY"] = self._old

    def test_round_end_clears_window_key(self):
        client = _Client()
        strategy = _Strategy()
        play_game(client, "g1", strategy)

        # ★ 断言口径修正（2026-09-23 R1147）：
        #   本测试真正要保护的**不变量是"提交了 2 个动作"**（跨局同窗口不被
        #   上一局的去重键吞掉）。而 R1105 之后 `response_*` 窗口每轮会额外跑一次
        #   **影子决策**（bot/game.py:744-754：把 my_hand/all_melds 换成缓存侧副本
        #   再 decide 一次，用于量化"缓存陈旧是否改变动作"，**该动作不提交**）
        #   ⇒ 原始 `strategy.calls` 恒为 2 真实 + N 影子，写死 ==2 会假失败。
        #   影子调用数量 = 窗口出现次数，故此处按"动作"断言、对 calls 只要求 ≥2。
        self.assertEqual(client.actions, [{"action": "pass", "tile": ""},
                                          {"action": "pass", "tile": ""}],
                         "跨局后再次出现相同 (phase,turn,offer) 窗口仍须重新决策")
        self.assertGreaterEqual(
            strategy.calls, 2,
            "两次窗口各至少一次真实决策（多余的是 R1105 影子探针，不提交）")


if __name__ == "__main__":
    unittest.main()
