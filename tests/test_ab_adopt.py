# -*- coding: utf-8 -*-
"""`tools/ab_adopt.py` 单测：**采用路径本身**必须可靠（它是在阈值到达那一刻才能真正捕获收益的一步）。

回归意义：此前只测过 REFUSE 路径与 --dry-run；真正执行时会
`ab_ctl stop` → 写生产策略 → 落证据。若这一步在关键时刻出错，前面的 A/B 就白跑了。
（不断言 `ab_ctl stop` 的副作用，subprocess 被替换。）
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("aba", os.path.join(ROOT, "tools", "ab_adopt.py"))
aba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aba)


def _run(arm):
    """调用 main 并吞掉它的打印（避免污染测试输出）。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return aba.main([arm])


def _mkrank(path, arm, nets, ts0="2026-09-16 00:00:00"):
    with io.open(path, "a", encoding="utf-8") as f:
        for i, n in enumerate(nets):
            other = -n / 3.0
            f.write(json.dumps({
                "ts": ts0, "strategy": arm,
                "ranking": [{"user_id": aba.ME, "total_score": n},
                            {"user_id": "a", "total_score": other},
                            {"user_id": "b", "total_score": other},
                            {"user_id": "c", "total_score": other}]}) + "\n")


class TestAbAdopt(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aba_")
        self.var = os.path.join(self.d, "var")
        os.makedirs(self.var)
        self.rank = os.path.join(self.var, "auto_ranking.jsonl")
        self.ab = os.path.join(self.var, ".ab_mode")
        self.strat = os.path.join(self.var, "_keeper_strategy.txt")
        self.log = os.path.join(self.var, "_ab_adopt_log.jsonl")
        io.open(os.path.join(self.d, "run_bot.py"), "w", encoding="utf-8").write(
            '"speedtugc" "speedc132"\n')
        io.open(self.strat, "w", encoding="utf-8").write("speedtugc")
        io.open(self.ab, "w", encoding="utf-8").write(json.dumps(
            {"arms": ["speedtugc", "speedc132"], "rooms": 1, "started": "2026-09-16 00:00:00"}))
        self._saved = (aba.ROOT, aba.AB, aba.STRAT_FILE, aba.LOG, aba.subprocess.call)
        aba.ROOT, aba.AB, aba.STRAT_FILE, aba.LOG = self.d, self.ab, self.strat, self.log
        self.calls = []
        aba.subprocess.call = lambda *a, **k: self.calls.append(a) or 0

    def tearDown(self):
        (aba.ROOT, aba.AB, aba.STRAT_FILE, aba.LOG, aba.subprocess.call) = self._saved

    def test_refuses_when_threshold_not_met(self):
        _mkrank(self.rank, "speedtugc", [10.0 + (i % 5) * 8 for i in range(12)])
        _mkrank(self.rank, "speedc132", [15.0 - (i % 5) * 8 for i in range(12)])   # 差太小
        rc = _run("speedc132")
        self.assertEqual(rc, 3, "未达阈值必须 REFUSE")
        self.assertEqual(self.calls, [], "REFUSE 时不得调用 ab_ctl stop")
        with io.open(self.strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "speedtugc", "REFUSE 时不得改策略文件")

    def test_adopts_winner_and_logs_evidence(self):
        # 12 房/臂、差距大且**有方差**（全同值会让 SD=0 ⇒ t 算不出来）
        _mkrank(self.rank, "speedtugc", [-60.0 + (i % 5) * 8 for i in range(12)])
        _mkrank(self.rank, "speedc132", [60.0 - (i % 5) * 8 for i in range(12)])
        rc = _run("speedc132")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 1, "应调用一次 ab_ctl stop")
        with io.open(self.strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "speedc132", "应采用较优臂")
        with io.open(self.log, encoding="utf-8") as f:
            ev = json.loads(f.readline())
        self.assertEqual(ev["chosen"], "speedc132")
        self.assertTrue(ev["threshold_met"])
        self.assertGreater(abs(ev["t"]), 3.0)
        self.assertEqual(ev["rooms"]["speedc132"], 12)

    def test_adopts_best_middle_arm_in_multi_arm(self):
        # 3 臂：c159 是最优的中间臂，旧实现只看 arms[-1] 会错误拒绝它。
        io.open(os.path.join(self.d, "run_bot.py"), "w", encoding="utf-8").write(
            "\"speedtugc\" \"speedc159\" \"speedc156\"\n")
        io.open(self.ab, "w", encoding="utf-8").write(json.dumps(
            {"arms": ["speedtugc", "speedc159", "speedc156"], "rooms": 1,
             "started": "2026-09-16 00:00:00"}))
        _mkrank(self.rank, "speedtugc", [-60.0 + (i % 5) * 8 for i in range(12)])
        _mkrank(self.rank, "speedc159", [60.0 - (i % 5) * 8 for i in range(12)])
        _mkrank(self.rank, "speedc156", [20.0 - (i % 5) * 8 for i in range(12)])
        rc = _run("speedc159")
        self.assertEqual(rc, 0, "中间臂达到阈值且为最优时必须可被采用")
        with io.open(self.strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "speedc159")

    def test_refuses_adopting_the_worse_arm(self):
        _mkrank(self.rank, "speedtugc", [-60.0 + (i % 5) * 8 for i in range(12)])
        _mkrank(self.rank, "speedc132", [60.0 - (i % 5) * 8 for i in range(12)])
        rc = _run("speedtugc")                            # 想采用较差的那一臂
        self.assertEqual(rc, 3)
        with io.open(self.strat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "speedtugc")


if __name__ == "__main__":
    unittest.main()

class TestAdoptVerdict(unittest.TestCase):
    """预登记判据（纯函数）：中期 |t|>=3 & >=12 房；终点 组合臂 1.50/150、单变量 1.96/100。"""

    def test_mid_term_rule(self):
        verdict = aba.verdict
        self.assertEqual(verdict(3.5, 12, 12, False), (True, "mid"))
        self.assertEqual(verdict(-3.5, 12, 12, False), (True, "mid"))   # 反向显著 ⇒ 采用"另一臂"

    def test_bundle_end_rule_needs_150(self):
        verdict = aba.verdict
        self.assertEqual(verdict(1.7, 160, 160, True), (True, "end"))
        self.assertEqual(verdict(1.7, 120, 120, True), (False, None))   # 样本不够

    def test_single_end_rule_needs_196(self):
        verdict = aba.verdict
        self.assertEqual(verdict(2.5, 120, 120, False), (True, "end"))
        self.assertEqual(verdict(1.7, 160, 160, False), (False, None))  # 单变量 1.7 不够

    def test_negative_never_accepted_by_end_rule(self):
        verdict = aba.verdict
        self.assertEqual(verdict(-2.5, 200, 200, True), (False, None))
        self.assertEqual(verdict(-1.6, 200, 200, False), (False, None))

class TestAdoptGuards(unittest.TestCase):
    """R691：**三道护栏**（原始 t / 桌强调整后 t / 第一率）—— 决策路径必须可测。

    为什么补：`ab_adopt` 是"阈值到达那一刻唯一能捕获收益的一步"。R658 加了桌强护栏、
    R663 加了第一率护栏，但当时的 8 项单测都写在它们之前 ⇒ **护栏本身没有被测过**。
    现在把三道判据集中到纯函数 `adopt_ok`，并在此钉住。
    """

    def test_guard2_blocks_when_adjusted_t_negative(self):
        """原始 t 很足，但**桌强调整后 t<0** ⇒ 不采用（防"房更容易"被读成"臂更强"）。"""
        ok, rule = aba.adopt_ok(3.5, -0.2, 1.0, 1.0, 20, False)
        self.assertFalse(ok)
        self.assertIsNone(rule)

    def test_guard3_blocks_when_first_rate_lower(self):
        """原始 t 与调整后 t 都过，但**候选第一率低于基线** ⇒ 不采用（预登记 §6／用户口径）。"""
        ok, rule = aba.adopt_ok(3.5, 1.0, 0.10, 0.30, 20, False)
        self.assertFalse(ok)
        self.assertIsNone(rule)

    def test_all_three_pass_mid(self):
        ok, rule = aba.adopt_ok(3.5, 0.5, 0.30, 0.25, 20, False)
        self.assertTrue(ok)
        self.assertEqual(rule, "mid")

    def test_end_rule_single_vs_bundle(self):
        # 单变量：100 房 + t≥1.96
        self.assertEqual(aba.adopt_ok(2.0, 0.1, 0.2, 0.2, 100, False), (True, "end"))
        # 组合臂：150 房 + t≥1.50
        self.assertEqual(aba.adopt_ok(1.6, 0.1, 0.2, 0.2, 150, True), (True, "end"))
        # 组合臂在 100 房时**不得**按终点采用（阈值/房数都不够）
        self.assertFalse(aba.adopt_ok(1.6, 0.1, 0.2, 0.2, 100, True)[0])
        # 单变量 150 房但 t<1.96 ⇒ 不采用
        self.assertFalse(aba.adopt_ok(1.9, 0.1, 0.2, 0.2, 150, False)[0])

    def test_first_rate_equal_is_allowed(self):
        """预登记是"不低于"⇒ 相等必须放行（否则会因舍入把好臂挡住）。"""
        ok, _rule = aba.adopt_ok(3.5, 0.5, 0.25, 0.25, 20, False)
        self.assertTrue(ok)

    def test_adj_stats_applies_beta_with_correct_sign(self):
        """β>0 ⇒ 对手越强，调整后净胜越低（钉住 `_adj_stats` 的符号与口径）。"""
        allr = {"A": [{"ts": "2026-09-16 00:00:00", "room": "r1", "net": 10.0, "first": False},
                      {"ts": "2026-09-16 00:00:01", "room": "r2", "net": 10.0, "first": False}]}
        ostr = {"r1": 0.0, "r2": 10.0}
        n, m, _se = aba._adj_stats("A", allr, "2026-09-16 00:00:00", ostr, 2.0)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(m, 0.0)          # (10−0 + 10−20)/2 = 0
        # 强度缺失的房按 beta=0 处理（不因缺数据把净值改掉）
        n2, m2, _ = aba._adj_stats("A", allr, "2026-09-16 00:00:00", {"r1": 0.0}, 2.0)
        self.assertEqual(n2, 2)
        # 缺强度的房按 beta=0 处理 ⇒ (10−0 + 10−0)/2 = 10（**不因缺数据而改动净值**）
        self.assertAlmostEqual(m2, 10.0)


class TestReducedBarRules(unittest.TestCase):
    """R884：预登记里写死、但工具此前**未实现**的两档 —— 临时采用 / 非劣性。

    为什么必须测：这两档是"小幅但机制成立的改进能否累积"的**唯一通道**；
    此前 `ab_adopt` 只实现了 mid/end，导致这两档判词出不来（只能 --force，丢审计语义）。
    """

    def test_provisional_needs_explicit_flag(self):
        """默认（未开档）时 t=1.5/100 房**不得**被采用（冻结档要 1.96）。"""
        self.assertFalse(aba.adopt_ok(1.5, 0.1, 0.2, 0.2, 100, False)[0])
        # 显式开"临时采用"档 ⇒ 通过
        self.assertEqual(aba.adopt_ok(1.5, 0.1, 0.2, 0.2, 100, False, mode="provisional"),
                         (True, "provisional"))

    def test_provisional_threshold_and_rooms(self):
        self.assertFalse(aba.adopt_ok(1.27, 0.1, 0.2, 0.2, 100, False, mode="provisional")[0])
        self.assertFalse(aba.adopt_ok(1.5, 0.1, 0.2, 0.2, 60, False, mode="provisional")[0])

    def test_noninf_adopts_slightly_negative(self):
        """非劣性：t 略负（>-1.28）且 100 房 ⇒ 采用（这是预登记明写的赌注）。"""
        self.assertEqual(aba.adopt_ok(-0.5, -0.2, 0.2, 0.2, 100, False, mode="noninf"),
                         (True, "noninf"))
        # 明确更差 ⇒ 不采用
        self.assertFalse(aba.adopt_ok(-1.5, -0.5, 0.2, 0.2, 100, False, mode="noninf")[0])

    def test_reduced_bars_still_blocked_by_first_rate(self):
        """两档都**保留**第一率护栏（用户裁定的主口径）。"""
        for m in ("provisional", "noninf"):
            self.assertFalse(aba.adopt_ok(1.5 if m == "provisional" else 0.5,
                                          0.1, 0.10, 0.30, 100, False, mode=m)[0])

    def test_end_takes_precedence_when_also_met(self):
        """若同时够终点档，应报**更强**的那一档（end），而不是降级档。"""
        self.assertEqual(aba.adopt_ok(2.0, 0.1, 0.2, 0.2, 100, False, mode="provisional"),
                         (True, "end"))

    def test_noninf_does_not_block_on_adjusted_t(self):
        """★ 有意的语义：非劣性档**不**把"桌强调整后 t>=0"当阻塞（预登记原文未要求），
        但 CLI 会打印提示。若将来要让第二道护栏也阻塞，此测试必须同步改。"""
        self.assertEqual(aba.adopt_ok(0.5, -0.4, 0.2, 0.2, 100, False, mode="noninf"),
                         (True, "noninf"))

