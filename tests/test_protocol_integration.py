"""协议层集成演练：mock 服务器驱动 run_tournament 完整状态流转。

场景剧本（模拟正式赛 v10 多阶段）：
  registering（报名+到位）→ running（两场并发收割）→ stage_done（等推进）
  → stage_open（阶段出席确认）→ running（新场）→ finished（退出）。
断言：注册/到位/确认调用、两场并发均被 play、终态退出、无 action 提交。
"""
import threading
import time
import unittest

import bot.protocol as protocol_mod
from bot.protocol import run_tournament
from bot.strategy import NaiveStrategy


def setUpModule():
    # 测试节奏：把稳态轮询缩短（生产值：REGISTER 15s / STAGE_WAIT 5s）
    protocol_mod.REGISTER_POLL = 1.2
    protocol_mod.STAGE_WAIT_POLL = 1.2


class FakeClient:
    """按剧本推进的假服务器。"""

    def __init__(self, script):
        # script: [(status, active_games, extra)]，extra 可带 qualified
        self.script = list(script)
        self.idx = 0
        self.register_calls = 0
        self.ready_calls = 0
        self.game_state_calls = []
        self.action_calls = []
        self.confirm_ok = False

    def _now(self):
        i = min(self.idx, len(self.script) - 1)
        return self.script[i]

    def advance(self):
        self.idx += 1

    # -- 玩家 API --
    def me(self):
        return {"user_id": "u_test", "tournament_id": "t_test",
                "active_games": [{"game_id": g} for g in self._now()[1]]}

    def tournament(self, tid):
        status = self._now()[0]
        extra = self._now()[2] if len(self._now()) > 2 else {}
        t = {"status": status, "my_games": ["g1", "g2", "g3"]}
        t.update(extra)
        return t

    def register(self, tid):
        self.register_calls += 1
        return {}

    def ready(self, tid):
        self.ready_calls += 1
        self.confirm_ok = True
        return {}

    # -- 对局 API（立即结束，防止真实打牌逻辑进入） --
    def game_state(self, gid, seq=0):
        self.game_state_calls.append(gid)
        return {"finished": True,
                "snapshot": {"seat": 0, "phase": "finished", "scores": {}}}

    def game_action(self, gid, action):
        self.action_calls.append((gid, action))
        return {}

    def guide_version(self):
        raise NotImplementedError


class TestTournamentIntegration(unittest.TestCase):
    def _script(self):
        return [
            ("registering", [], {}),
            ("running", ["g1", "g2"], {}),
            ("stage_done", [], {"stage": {"no": 1, "name": "测试-第1轮"}}),
            ("stage_open", [], {"qualified": True,
                                "stage": {"no": 2, "name": "测试-第2轮"}}),
            ("running", ["g3"], {}),
            ("finished", [], {}),
        ]

    def test_full_flow(self):
        fc = FakeClient(self._script())

        def driver():
            # 每 ~1.2s 推进一个剧本状态
            for _ in range(len(self._script())):
                time.sleep(1.2)
                fc.advance()

        th = threading.Thread(target=driver, daemon=True)
        th.start()
        result = run_tournament(fc, "t_test", NaiveStrategy(), scoped=True)
        th.join(timeout=30)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "finished")
        self.assertGreaterEqual(fc.register_calls, 1, "应至少报名一次")
        self.assertGreaterEqual(fc.ready_calls, 2, "应报名期到位 + stage_open 确认")
        # 两场并发收割：g1 g2 都进过 game_state；stage2 新场 g3 也被收割
        self.assertIn("g1", fc.game_state_calls)
        self.assertIn("g2", fc.game_state_calls)
        self.assertIn("g3", fc.game_state_calls)
        self.assertEqual(fc.action_calls, [], "本演练不应提交任何对局动作")

    def test_eliminated_exit(self):
        """stage_open 名单外（qualified=False）→ 干净退出。"""
        fc = FakeClient([
            ("registering", [], {}),
            ("stage_open", [], {"qualified": False,
                                "stage": {"no": 2, "name": "测试-第2轮"}}),
        ])

        def driver():
            time.sleep(1.6)
            fc.advance()

        threading.Thread(target=driver, daemon=True).start()
        result = run_tournament(fc, "t_test", NaiveStrategy(), scoped=True)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "stage_open")
        self.assertGreaterEqual(fc.register_calls, 1)
        self.assertEqual(fc.ready_calls, 1)   # 仅报名期到位，未做阶段确认


if __name__ == "__main__":
    unittest.main()
