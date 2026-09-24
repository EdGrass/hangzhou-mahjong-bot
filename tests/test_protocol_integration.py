"""协议层集成演练（行为驱动，确定性）：mock 服务器驱动 run_tournament。

剧本：registering（报名+到位）→ running（两场并发收割 g1/g2）
  → stage_done（等推进）→ stage_open（阶段出席确认）→ running（新场 g3）
  → finished（退出）。测试主线程按「动作发生即推进」驱动，无时间竞态。
"""
import threading
import time
import unittest

from unittest import mock

from bot import protocol as protocol_module
from bot.api import ApiError
from bot.protocol import run_tournament
from bot.speed import SpeedBase


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.idx = 0
        self.register_calls = 0
        self.ready_calls = 0
        self.game_state_calls = []
        self.action_calls = []

    def _now(self):
        return self.script[min(self.idx, len(self.script) - 1)]

    def advance(self):
        self.idx += 1

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
        if self._now()[0] in ("finished", "closed", "void"):
            # 终态后 ready：正式锦标赛 409（测试房跨轮待机则不应走到终态剧本）
            raise ApiError(409, "TOURNAMENT_CLOSED")
        return {}

    def game_state(self, gid, seq=0):
        self.game_state_calls.append(gid)
        return {"finished": True,
                "snapshot": {"seat": 0, "phase": "finished", "scores": {}}}

    def game_action(self, gid, action):
        self.action_calls.append((gid, action))
        return {}


class TestTournamentIntegration(unittest.TestCase):
    """把主循环的生产轮询间隔压到毫秒级（只在本测试类内生效）。

    bot/protocol.py 的 POLL_INTERVAL/REGISTER_POLL/... 是为线上低频轮询
    （防限流）设的墙钟常量；单测只关心状态机**推进逻辑**，不该真睡 15 秒
    —— 那会让 join(timeout=30) 在满负载跑全量时余量耗尽而假红。
    生产代码原样不动。
    """

    _FAST_TIMING = {
        "POLL_INTERVAL": 0.05,
        "REGISTER_POLL": 0.05,
        "STAGE_WAIT_POLL": 0.05,
        "UNKNOWN_STATUS_INTERVAL": 0.05,
    }

    def setUp(self):
        self._timing_patches = [
            mock.patch.object(protocol_module, name, value)
            for name, value in self._FAST_TIMING.items()
        ]
        for p in self._timing_patches:
            p.start()
        self.addCleanup(self._stop_patches)

    def _stop_patches(self):
        for p in reversed(self._timing_patches):
            p.stop()

    def _wait_until(self, cond, timeout=25):
        t0 = time.time()
        while not cond() and time.time() - t0 < timeout:
            time.sleep(0.05)
        self.assertTrue(cond(), "条件超时未满足")

    def _run_in_thread(self, fc):
        res = {}

        def runner():
            res["result"] = run_tournament(fc, "t_test", SpeedBase(), scoped=True)

        th = threading.Thread(target=runner, daemon=True)
        th.start()
        return th, res

    def test_full_flow(self):
        fc = FakeClient([
            ("registering", [], {}),
            ("running", ["g1", "g2"], {}),
            ("stage_done", [], {"stage": {"no": 1, "name": "测试-第1轮"}}),
            ("stage_open", [], {"qualified": True,
                                "stage": {"no": 2, "name": "测试-第2轮"}}),
            ("running", ["g3"], {}),
            ("finished", [], {}),
        ])
        th, res = self._run_in_thread(fc)
        # 报名+到位完成后推进到 running
        self._wait_until(lambda: fc.register_calls >= 1 and fc.ready_calls >= 1)
        fc.advance()
        # 双场并发收割后推进
        self._wait_until(lambda: "g1" in fc.game_state_calls
                         and "g2" in fc.game_state_calls)
        fc.advance()
        # stage_done 空转 → 推进到 stage_open
        time.sleep(1.0)
        fc.advance()
        # 阶段出席确认（ready 第二次）→ 推进到 running[g3]
        self._wait_until(lambda: fc.ready_calls >= 2)
        fc.advance()
        # g3 收割后推进到 finished
        self._wait_until(lambda: "g3" in fc.game_state_calls)
        fc.advance()
        th.join(timeout=25)
        self.assertIsNotNone(res.get("result"))
        self.assertEqual(res["result"]["status"], "finished")
        self.assertGreaterEqual(fc.register_calls, 1)
        self.assertGreaterEqual(fc.ready_calls, 2)
        self.assertEqual(fc.action_calls, [], "本演练不应提交任何对局动作")

    def test_eliminated_exit(self):
        fc = FakeClient([
            ("registering", [], {}),
            ("stage_open", [], {"qualified": False,
                                "stage": {"no": 2, "name": "测试-第2轮"}}),
        ])
        th, res = self._run_in_thread(fc)
        self._wait_until(lambda: fc.register_calls >= 1 and fc.ready_calls >= 1)
        fc.advance()            # → stage_open 名单外
        th.join(timeout=30)
        self.assertIsNotNone(res.get("result"))
        self.assertEqual(res["result"]["status"], "stage_open")
        self.assertEqual(fc.ready_calls, 1)   # 仅报名期到位，未做阶段确认


if __name__ == "__main__":
    unittest.main()

