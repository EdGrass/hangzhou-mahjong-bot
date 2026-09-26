# -*- coding: utf-8 -*-
"""读数工具的 **N 臂支持**（R1482）。

为什么要钉：役 3 是三臂，`.ab_mode` 是 `{"arms":[...]}`；而一批读数工具只读
`a`/`b`（两臂时代）⇒ 在役 3 下输出“None vs None / 数据不足”，
而 `_gate_report.py`（八步全链路彩排）会把这些步骤记为失败。

本轮发现并修的三个：
  · `var/_first_rate_readout.py`（第一率——**用户只看这个**）只读 a/b ⇒ 返回 1；
  · `var/_breaker_watch.py`（熔断余量）只读 a/b；且它连 `--since` 都不接受
    （`_gate_report.py` 传了，旧版静默忽略）；
  · `var/_power_two_endpoints.py` 默认臂写死为 `speedtugc`/`speedc151`，且读 `.ab_mode` 时
    **漏了 `import io`**（`NameError` 被 `except Exception` 吃掉）⇒ 静默落回错的默认臂。
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import _first_rate_readout as FR  # noqa: E402
import _breaker_watch as BW       # noqa: E402
import _power_two_endpoints as PW  # noqa: E402

NARM = {"arms": ["speedvalue", "speedvaluebc", "speedvaluebaotouv5"],
         "bundles": ["speedvalue"]}
LEGACY = {"a": "speedc151", "b": "speedvalue", "bundles": ["speedc151"]}


class TestArmsOf(unittest.TestCase):
    def test_first_rate_n_arm(self):
        self.assertEqual(3, len(FR.arms_of(NARM)))
        self.assertEqual("speedvaluebc", FR.arms_of(NARM)[1])

    def test_first_rate_legacy(self):
        self.assertEqual(["speedc151", "speedvalue"], FR.arms_of(LEGACY))

    def test_first_rate_empty(self):
        self.assertEqual([], FR.arms_of({}))

    def test_breaker_n_arm(self):
        self.assertEqual(3, len(BW.arms_of(NARM)))

    def test_breaker_legacy_and_empty(self):
        self.assertEqual(["speedc151", "speedvalue"], BW.arms_of(LEGACY))
        self.assertEqual([], BW.arms_of({}))


class TestFirstRateArmsOverride(unittest.TestCase):
    """★ R1552：`--arms` 覆盖 + 缺 `since` 时**明确拒绝**。

    为什么：该工具原本**只能从 `.ab_mode` 取臂集** ⇒ 役已收口（没有 `.ab_mode`）时
    直接输出“读不到臂集” —— 而 10/5 的 §V.66 破平第③步正是**第1率**。
    同时：拿不到 `since` 就不能拿“全时段”数字冒充役次读数。
    """

    def _run(self, argv, mode):
        import contextlib, io as _io
        from unittest import mock
        old_report = FR._report
        seen = []
        FR._report = lambda b, c, s: seen.append((b, c, s)) or 0
        try:
            buf = _io.StringIO()
            with mock.patch.object(FR, "_mode", mode), mock.patch.object(sys, "argv", argv), \
                 contextlib.redirect_stdout(buf):
                rc = FR.main()
        finally:
            FR._report = old_report
        return rc, seen, buf.getvalue()

    def test_arms_override_works_without_ab_mode(self):
        def _boom(*a, **k):
            raise RuntimeError("no .ab_mode")
        rc, seen, out = self._run(
            ["x", "--arms", "speedvalue,speedvaluebc,speedvaluebaotouv5", "--since", "T"], _boom)
        self.assertEqual(0, rc, out)
        self.assertEqual([("speedvalue", "speedvaluebc", "T"),
                          ("speedvalue", "speedvaluebaotouv5", "T")], seen)

    def test_missing_since_is_refused(self):
        def _boom(*a, **k):
            raise RuntimeError("no .ab_mode")
        rc, seen, out = self._run(["x", "--arms", "speedvalue,speedvaluebc"], _boom)
        self.assertEqual(1, rc, out)
        self.assertEqual([], seen)
        self.assertIn(u"需要 --since", out)


class TestPowerArmsFromCfg(unittest.TestCase):
    def test_n_arm_derives_base_and_first_candidate(self):
        base, cand = PW.arms_from_cfg(NARM)
        self.assertEqual("speedvalue", base)
        self.assertEqual("speedvaluebc", cand)

    def test_legacy(self):
        base, cand = PW.arms_from_cfg(LEGACY)
        self.assertEqual("speedc151", base)
        self.assertEqual("speedvalue", cand)

    def test_empty_is_safe(self):
        self.assertEqual(("", ""), PW.arms_from_cfg({}))

    def test_reads_real_abmode_shape(self):
        # 真实役 3 配置的字段名必须被认得（防字段改名后静默失效）
        cfg = {"arms": ["speedvalue", "speedvaluebc", "speedvaluebaotouv5"],
               "rooms": 1, "started": "2026-09-25 20:52:39", "bundles": ["speedvalue"]}
        self.assertEqual(("speedvalue", "speedvaluebc"), PW.arms_from_cfg(cfg))


if __name__ == "__main__":
    unittest.main()
