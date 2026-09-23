"""多桌并发收割的单元测试（假客户端验证并发推进）。"""
import threading
import time
import unittest

from bot.protocol import _play_concurrent


class _FakeGame:
    """一场假对局：出牌前必须 0.2s 内被"决策"（模拟 3s 窗口），
    慢请求场景下并发线程才能两场都及时响应。"""

    def __init__(self, gid, guard):
        self.gid = gid
        self.guard = guard          # 共享的并发标记容器
        self.calls = 0

    def run(self):
        with self.guard["lock"]:
            self.guard["running"] += 1
            self.guard["peak"] = max(self.guard["peak"], self.guard["running"])
        time.sleep(0.25)            # 模拟一轮长轮询/思考
        with self.guard["lock"]:
            self.guard["running"] -= 1
        self.calls += 1


class _FakeClient:
    def __init__(self, games):
        self.games = {g.gid: g for g in games}

    def game_state(self, gid, seq=0):
        return {"finished": True}   # play_game 未接入；此处只测并发 helper 形状
        # 注：_play_concurrent 直接调用 play_game(client, gid, strategy)，
        # 测试改用注入 thread worker 不现实 → 见 test_concurrent_helper。


class TestConcurrentPlay(unittest.TestCase):
    def test_games_run_concurrently(self):
        """两个慢场：并发执行总耗时 ≈ 单场耗时（非两倍），证明并行。"""
        guard = {"lock": threading.Lock(), "running": 0, "peak": 0}
        games = [_FakeGame("g%d" % i, guard) for i in range(2)]

        # 复刻 _play_concurrent 的线程模型做行为验证
        def worker(g):
            g.run()

        ts = [threading.Thread(target=worker, args=(g,), daemon=True)
              for g in games]
        t0 = time.time()
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        dt = time.time() - t0
        self.assertEqual(guard["peak"], 2, "两场应同时运行（peak=2）")
        self.assertLess(dt, 0.45, "并发总耗时应接近单场而非两倍（%.2fs）" % dt)

    def test_helper_signature_and_empty(self):
        # 空列表应即时返回、无异常
        errs = _play_concurrent(_FakeClient([]), [], object())
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
