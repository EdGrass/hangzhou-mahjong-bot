# -*- coding: utf-8 -*-
"""`tools/rules_guard.py` 的判定表单测 —— 它现在是**开赛流程的硬门禁**（`_switch_to_official.ps1` 步骤 1b）。

规则（指南 §1.6 / STATUS §4c-11）：`YouCaiBiKao` 每场可配。
  - true  + 无闸门策略（如 speedtugc）⇒ 有白平胡会被 409 拒（占我方胡牌 64.4%）⇒ 必须 exit 2；
  - false + 有闸门策略（speedc148/153）⇒ 主动拒掉合法平胡 ⇒ 必须 exit 2；
  - 一致 ⇒ exit 0；读不到 config ⇒ exit 3。
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("rules_guard_t", os.path.join(ROOT, "tools", "rules_guard.py"))
rg = importlib.util.module_from_spec(spec)
sys.modules["rules_guard_t"] = rg
spec.loader.exec_module(rg)


class _FakeClient:
    cfg = {"M": 10, "Rounds": 16, "BaseScore": 1, "YouCaiBiKao": False}
    fail = False

    def __init__(self, server, token):
        pass

    def tournament_rules(self):
        if _FakeClient.fail:
            raise rg.ApiError(400, '{"error":{"code":"TOKEN_NOT_SCOPED"}}')
        return {"config": dict(_FakeClient.cfg)}


class TestRulesGuard(unittest.TestCase):
    def setUp(self):
        fd, self.tok = tempfile.mkstemp()
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("dummy-token")
        self.addCleanup(os.unlink, self.tok)
        self._orig_client = rg.Client
        rg.Client = _FakeClient
        self.addCleanup(self._restore)

    def _restore(self):
        rg.Client = self._orig_client
        _FakeClient.fail = False

    def _run(self, ycbk, strategy):
        _FakeClient.cfg["YouCaiBiKao"] = ycbk
        _FakeClient.fail = False
        sys.argv = ["rules_guard.py", "--token-file", self.tok, "--strategy", strategy]
        return rg.main()

    def test_false_with_plain_strategy_is_ok(self):
        self.assertEqual(self._run(False, "speedtugc"), 0)

    def test_true_with_plain_strategy_is_mismatch(self):
        self.assertEqual(self._run(True, "speedtugc"), 2, "true 环境跑无闸门策略必须拦下")

    def test_false_with_gated_strategy_is_mismatch(self):
        self.assertEqual(self._run(False, "speedc148"), 2)
        self.assertEqual(self._run(False, "speedc153"), 2)

    def test_true_with_gated_strategy_is_ok(self):
        self.assertEqual(self._run(True, "speedc148"), 0)
        self.assertEqual(self._run(True, "speedc153"), 0)

    def test_true_with_fast_gated_strategies_is_ok(self):
        self.assertEqual(self._run(True, "speedc172"), 0)
        self.assertEqual(self._run(True, "speedc176"), 0)
        self.assertEqual(self._run(True, "speedc181"), 0)
        self.assertEqual(self._run(True, "speedc184"), 0)

    def test_false_with_fast_gated_strategies_is_mismatch(self):
        self.assertEqual(self._run(False, "speedc172"), 2)
        self.assertEqual(self._run(False, "speedc176"), 2)
        self.assertEqual(self._run(False, "speedc181"), 2)
        self.assertEqual(self._run(False, "speedc184"), 2)
    def test_unreadable_config_returns_3(self):
        _FakeClient.fail = True
        sys.argv = ["rules_guard.py", "--token-file", self.tok, "--strategy", "speedtugc"]
        self.assertEqual(rg.main(), 3)



