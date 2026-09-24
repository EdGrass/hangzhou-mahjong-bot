# -*- coding: utf-8 -*-
"""R1147 回归：锦标赛详情**瞬态 404** 不得立刻判"房间已删除"。

背景（2026-09-23 三测报名期实测）：`run_tournament` 的 404 容错写成

    if now404 - last_404_at > 120:      # last_404_at 初值 0.0
        ...退出

而 `last_404_at` 初值为 0.0 ⇒ **第一次** 404 就满足 `1.79e9 - 0 > 120`
⇒ 任何一次服务器重启瞬态 404 都会立刻杀掉 run_bot（实测 16:58 起跑 11 分钟，
17:09:53 撞上第一个 404 即退出；正式赛里等价于**对局中途无故重启**）。

本测试钉住三件事：
  ① 单个瞬态 404 ⇒ 继续轮询，不退出；
  ② 连续 3 次 404 ⇒ 仍继续（未超 120s 宽限）；
  ③ **只有**连续 404 超过 120s 才退出；
  ④ 中途成功拿到详情 ⇒ 404 计时清零（两次 404 间隔 >120s 也不得误判）。
"""
import inspect
import itertools
import unittest
from unittest import mock

from bot import protocol as protocol_module
from bot.api import ApiError
from bot.protocol import run_tournament
from bot.speed import SpeedBase

# ★ R1353：补丁是否已落地（B 段才落）—— 以“源码里有没有新引入的错误码”为判据（补丁前该字符串在该模块不存在，已核）。
PATCHED = "TOURNAMENT_NOT_FOUND" in inspect.getsource(protocol_module)


class _ScriptedClient:
    """按脚本回放 tournament() 响应。

    脚本元素：404 = 抛 ApiError(404)；其余字符串 = 该轮 status（最后一项会重复）。
    """

    def __init__(self, script, code="TOURNAMENT_GONE"):
        self.script = list(script)
        self.code = code
        self.calls = 0
        self.ready_calls = 0

    def _item(self):
        return self.script[min(self.calls - 1, len(self.script) - 1)]

    def tournament(self, tid):
        self.calls += 1
        item = self._item()
        if item == 404:
            raise ApiError(404, '{"code":"%s"}' % self.code)
        return {"status": item, "my_games": [], "ranking": []}

    def register(self, tid):
        return {}

    def ready(self, tid):
        self.ready_calls += 1
        if self._item() in ("finished", "closed", "void"):
            raise ApiError(409, "TOURNAMENT_CLOSED")
        return {}

    def me(self):
        return {"user_id": "u_test", "tournament_id": "t_test", "active_games": []}


class TestTransient404(unittest.TestCase):
    def _run(self, client, clock=None):
        with mock.patch.object(protocol_module.time, "sleep", lambda _s: None):
            if clock is None:
                return run_tournament(client, "t_test", SpeedBase(), scoped=True)
            with mock.patch.object(protocol_module.time, "time", clock):
                return run_tournament(client, "t_test", SpeedBase(), scoped=True)

    def test_single_404_is_tolerated(self):
        """① 首个 404 必须被当成瞬态，而不是"持续 >2min"。"""
        c = _ScriptedClient([404, "finished"])
        res = self._run(c)
        self.assertIsNotNone(res, "首个瞬态 404 被误判为『房间已删除』直接退出了")
        self.assertEqual(c.calls, 2, "首个 404 后没有继续轮询")

    def test_three_consecutive_404_tolerated(self):
        """② 连续 3 次 404（远低于 120s 宽限）仍应继续。"""
        c = _ScriptedClient([404, 404, 404, "finished"])
        res = self._run(c)
        self.assertIsNotNone(res)
        self.assertEqual(c.calls, 4)

    @unittest.skipIf(PATCHED, "P0 补丁已落地 ⇒ 旧契约（持续 404 超 120s 即退出）已被取代（见下两条）")
    def test_persistent_404_over_grace_exits(self):
        """③（补丁前）连续 404 超 120s ⇒ 才判房间真删并抛出。"""
        ticks = iter(range(0, 10 ** 6, 30))

        def fake_time():
            return float(next(ticks))

        c = _ScriptedClient([404])
        with self.assertRaises(ApiError):
            self._run(c, clock=fake_time)

    @unittest.skipUnless(PATCHED, "P0 补丁未落地（役间 B 段前）⇒ 新契约测试暂不适用")
    def test_gone_keeps_retrying_after_grace(self):
        """补丁后：`TOURNAMENT_GONE` = 房**暂时**不可达 ⇒ **不得因“持续 >120s”退出**（实测曾把 29 次 GONE 误判成房已删）。"""
        c = _ScriptedClient([404, 404, 404, 404, "finished"])
        res = self._run(c, clock=lambda: float(next(itertools.count(0, 30))))
        self.assertIsNotNone(res, "补丁后 GONE 仍被按“持续 >120s”误判退出")
        self.assertEqual(c.calls, 5, "补丁后 GONE 应继续轮询直到取到详情")

    @unittest.skipUnless(PATCHED, "P0 补丁未落地（役间 B 段前）⇒ 新契约测试暂不适用")
    def test_not_found_exits_immediately(self):
        """补丁后：`TOURNAMENT_NOT_FOUND` = 房**不存在** ⇒ **立刻放弃**（不重试）。"""
        c = _ScriptedClient([404], code="TOURNAMENT_NOT_FOUND")
        with self.assertRaises(ApiError):
            self._run(c)
        self.assertEqual(c.calls, 1, "NOT_FOUND 必须立刻放弃（不得重试）")

    def test_success_resets_404_timer(self):
        """④ 404 → 成功 → 再 404（两次间隔 180s）不得误判为持续 404。"""
        ticks = iter(range(0, 10 ** 6, 90))

        def fake_time():
            return float(next(ticks))

        c = _ScriptedClient([404, "registering", 404, "finished"])
        res = self._run(c, clock=fake_time)
        self.assertIsNotNone(res, "成功取得详情后 404 计时未清零，第二次 404 被误判")
        self.assertEqual(c.calls, 4)


if __name__ == "__main__":
    unittest.main()
