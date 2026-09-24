# -*- coding: utf-8 -*-
"""熔断器单测：验证判定逻辑 + 历史崩坏可被捕获 + 好策略不被误伤。"""
import importlib.util
import io
import json
import os
import contextlib
import io as _io
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rg", os.path.join(ROOT, "tools", "rate_guard.py"))
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)


class TestRateGuard(unittest.TestCase):
    def setUp(self):
        """隔离三个「哨兵文件」——否则线上真的存在 .official_mode / .ab_mode 时，
        这些端到端用例会因为 main() 提前让路而失败（本类曾经就是这种脆弱写法）。"""
        self._sent = (rg.OFFICIAL_FLAG, rg.AB_FLAG, rg.GUARD_OFF)
        d = tempfile.mkdtemp(prefix="rgflags_")
        rg.OFFICIAL_FLAG = os.path.join(d, ".official_mode")     # 都不存在
        rg.AB_FLAG = os.path.join(d, ".ab_mode")
        rg.GUARD_OFF = os.path.join(d, ".rate_guard_off")

    def tearDown(self):
        rg.OFFICIAL_FLAG, rg.AB_FLAG, rg.GUARD_OFF = self._sent

    def test_no_trip_below_window(self):
        trip, mean, n = rg.verdict([-300.0, -300.0])
        self.assertFalse(trip, "样本不足时绝不动作")
        self.assertEqual(n, 2)

    def test_trip_on_catastrophic_window(self):
        trip, mean, n = rg.verdict([-200.0] * rg.WINDOW)
        self.assertTrue(trip)
        self.assertEqual(n, rg.WINDOW)

    def test_no_trip_on_normal_window(self):
        trip, _, _ = rg.verdict([20.0, -40.0, 10.0, 0.0, -30.0, 25.0])
        self.assertFalse(trip)

    def test_uses_only_last_window(self):
        # 前面很好、最后窗口很烂 → 应触发（只看最近）
        nets = [500.0] * 10 + [-200.0] * rg.WINDOW
        trip, mean, n = rg.verdict(nets)
        self.assertTrue(trip)
        self.assertAlmostEqual(mean, -200.0)

    def test_recent_nets_reads_tail_and_skips_bad_rows(self):
        recs = []
        for i, sc in enumerate([10, 20, 30, 40]):
            recs.append({"strategy": "s%d" % i, "ranking": [
                {"user_id": rg.ME, "total_score": sc},
                {"user_id": "a", "total_score": 0},
                {"user_id": "b", "total_score": 0},
                {"user_id": "c", "total_score": 0}]})
        recs.append({"strategy": "broken", "ranking": []})       # 应被跳过
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
            path = f.name
        try:
            nets = rg.recent_nets(3, path=path)
        finally:
            os.unlink(path)
        self.assertEqual(nets, [20.0, 30.0, 40.0],
                         "应取最近 3 房且跳过无 ranking 的行")

    def test_threshold_is_conservative(self):
        """真实均值 0、SD 146 时，6 房窗口触发概率应 <2%。"""
        import random, statistics
        random.seed(7)
        trips = 0
        trials = 2000
        for _ in range(trials):
            w = [random.gauss(0, 146) for _ in range(rg.WINDOW)]
            if statistics.mean(w) < rg.THRESHOLD:
                trips += 1
        self.assertLess(trips / trials, 0.02,
                        "误伤率过高：%.3f" % (trips / trials))


    def test_main_reverts_and_logs_on_trip(self):
        """端到端（隔离路径）：6 房崩坏 → 写回退策略 + 记日志。
        kill_keeper 被替换，防止误杀线上 keeper。"""
        import tempfile
        d = tempfile.mkdtemp(prefix="rg_")
        ranking = os.path.join(d, "ranking.jsonl")
        strat = os.path.join(d, "strat.txt")
        logf = os.path.join(d, "guard.log")
        with open(ranking, "w", encoding="utf-8") as f:
            for _ in range(rg.WINDOW):
                f.write(json.dumps({"strategy": "badexp", "ranking": [
                    {"user_id": rg.ME, "total_score": -200},
                    {"user_id": "a", "total_score": 60},
                    {"user_id": "b", "total_score": 70},
                    {"user_id": "c", "total_score": 70}]}) + "\n")
        with open(strat, "w", encoding="utf-8") as f:
            f.write("badexp")
        old = (rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.kill_keeper)
        old_argv = list(sys.argv)
        killed = []
        rg.RANKING, rg.STRAT_FILE, rg.LOG = ranking, strat, logf
        rg.kill_keeper = lambda: killed.append(1)
        sys.argv = ["rate_guard.py"]
        buf = _io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):      # 不污染测试输出
                rc = rg.main()
        finally:
            rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.kill_keeper = old
            sys.argv = old_argv
        self.assertEqual(rc, 0)
        with open(strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), rg.FALLBACK, "应把策略文件写成回退目标")
        with open(logf, encoding="utf-8") as f:
            self.assertIn(rg.FALLBACK, f.read(), "应记录熔断日志")
        self.assertEqual(len(killed), 1, "应调用一次 kill_keeper")

    def test_ab_mode_defers_and_touches_nothing(self):
        """A/B 模式必须**完全让路**：排批与候选熔断归 _ab_driver.py。

        回归意义（2026-09-16）：慢档已触发（近 40 房 −47.6），若本工具在 A/B 期间动手，
        会把策略文件回退成 FALLBACK、并在「match_super 存活、run_bot 不在」的房与房之间
        **杀掉 A/B 正在轮转的那一批** ⇒ 两臂失衡、实验报废。
        """
        import tempfile
        d = tempfile.mkdtemp(prefix="rgab_")
        ranking = os.path.join(d, "ranking.jsonl")
        strat = os.path.join(d, "strat.txt")
        abflag = os.path.join(d, ".ab_mode")
        with open(ranking, "w", encoding="utf-8") as f:
            for _ in range(rg.LONG_WINDOW):          # 足够触发慢档
                f.write(json.dumps({"strategy": "speedtugc", "ranking": [
                    {"user_id": rg.ME, "total_score": -200},
                    {"user_id": "a", "total_score": 60},
                    {"user_id": "b", "total_score": 70},
                    {"user_id": "c", "total_score": 70}]}) + "\n")
        with open(strat, "w", encoding="utf-8") as f:
            f.write("speedtugc")
        open(abflag, "w").close()
        old = (rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.AB_FLAG, rg.kill_keeper,
               list(sys.argv))
        calls = []
        rg.RANKING, rg.STRAT_FILE, rg.AB_FLAG = ranking, strat, abflag
        rg.kill_keeper = lambda: calls.append("keeper")
        sys.argv = ["rate_guard.py"]
        try:
            with contextlib.redirect_stdout(_io.StringIO()) as buf:
                rc = rg.main()
        finally:
            (rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.AB_FLAG, rg.kill_keeper,
             sys.argv) = old
        self.assertEqual(rc, 0)
        self.assertNotIn("keeper", calls, "A/B 期间绝不能杀 keeper")
        with open(strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "speedtugc", "A/B 期间绝不能改策略文件")

    def test_ms_strategy_parsing(self):
        self.assertEqual(rg._ms_strategy(["python", "match_super.py", "--rooms", "4",
                                          "--strategy", "speedtugc"]), "speedtugc")
        self.assertIsNone(rg._ms_strategy(["python", "match_super.py"]))

    def test_main_cleans_up_match_super_even_when_already_on_fallback(self):
        """回归：策略文件已回退、但 match_super 仍跑旧策略时，必须继续收尾
        （否则回退要等整个批次 ≈1h 才生效）。"""
        import tempfile
        d = tempfile.mkdtemp(prefix="rg2_")
        ranking = os.path.join(d, "ranking.jsonl")
        strat = os.path.join(d, "strat.txt")
        with open(ranking, "w", encoding="utf-8") as f:
            for _ in range(rg.WINDOW):
                f.write(json.dumps({"strategy": rg.FALLBACK, "ranking": [
                    {"user_id": rg.ME, "total_score": -200},
                    {"user_id": "a", "total_score": 60},
                    {"user_id": "b", "total_score": 70},
                    {"user_id": "c", "total_score": 70}]}) + "\n")
        with open(strat, "w", encoding="utf-8") as f:
            f.write(rg.FALLBACK)                    # 已经是回退目标
        old = (rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.kill_keeper,
               rg.kill_match_super_if_idle, list(sys.argv))
        calls = []
        rg.RANKING, rg.STRAT_FILE = ranking, strat
        rg.kill_keeper = lambda: calls.append("keeper")
        rg.kill_match_super_if_idle = lambda expected=None: calls.append(("ms", expected))
        sys.argv = ["rate_guard.py"]
        try:
            with contextlib.redirect_stdout(_io.StringIO()):
                rg.main()
        finally:
            (rg.RANKING, rg.STRAT_FILE, rg.LOG, rg.kill_keeper,
             rg.kill_match_super_if_idle, sys.argv) = old
        self.assertNotIn("keeper", calls, "已是回退目标时不应再杀 keeper（避免churn）")
        self.assertIn(("ms", rg.FALLBACK), calls, "应继续收尾跑旧策略的 match_super")

    def test_slow_tier_fires_on_persistent_bleed(self):
        """慢档：不崩但持续失血（-60/房 × 40 房）也要熔断 —— 快档永远抓不到这种。"""
        nets = [-60.0] * rg.LONG_WINDOW
        trip, mean, n = rg.verdict(nets)
        self.assertTrue(trip, "持续失血必须能触发")
        self.assertAlmostEqual(mean, -60.0)

    def test_fast_tier_takes_precedence_and_reports_its_window(self):
        nets = [10.0] * (rg.LONG_WINDOW - rg.WINDOW) + [-200.0] * rg.WINDOW
        trip, mean, n = rg.verdict(nets)
        self.assertTrue(trip)
        self.assertEqual(n, rg.WINDOW, "应报告快档窗口大小")

    def test_slow_tier_boundary_just_above_threshold(self):
        """慢档阈值上方的 -30/房 不应触发（边界两侧都要有断言）。"""
        trip, mean, _ = rg.verdict([-30.0] * rg.LONG_WINDOW)
        self.assertFalse(trip, "-30/房 高于慢档阈值 -40，不应熔断")
        trip2, _, _ = rg.verdict([-50.0] * rg.LONG_WINDOW)
        self.assertTrue(trip2, "-50/房 低于慢档阈值 -40，应熔断")

    def test_mildly_negative_is_not_tripped(self):
        trip, _, _ = rg.verdict([-20.0] * rg.LONG_WINDOW)
        self.assertFalse(trip, "-20/房 属噪声范围，不应熔断")

if __name__ == "__main__":
    unittest.main()
