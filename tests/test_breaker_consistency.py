# -*- coding: utf-8 -*-
"""★ R1555：熔断器的**真身**（`_ab_driver`）与它的**读数**（`_breaker_watch`）必须**同参数**。

为什么：`_breaker_watch` 的 docstring 自己写着“把 `_ab_driver.py` 的熔断判据**复刻**成
‘当前离阈值多远’”。两处的 k/阈值一旦漂移，判词当天看到的就是**假的余量**
（比如报 OK 而实际已经会触发，或反之），而这种漂移是**静默**的。
"""
from __future__ import annotations
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "var"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class TestBreakerReadoutMatchesDriver(unittest.TestCase):
    def setUp(self):
        self.drv = _load("brk_drv_t", "var/_ab_driver.py")
        self.bw = _load("brk_bw_t", "var/_breaker_watch.py")

    def test_k_and_thresholds_are_identical(self):
        self.assertEqual(self.drv.GUARD_MIN_ROOMS, self.bw.FAST_K,
                         u"快档 k 不一致（真身 vs 读数）")
        self.assertEqual(self.drv.GUARD_NET, self.bw.FAST_THR,
                         u"快档阈值不一致（真身 vs 读数）")
        self.assertEqual(self.drv.GUARD_MILD_ROOMS, self.bw.MILD_K,
                         u"慢档 k 不一致（真身 vs 读数）")
        self.assertEqual(self.drv.GUARD_MILD_NET, self.bw.MILD_THR,
                         u"慢档阈值不一致（真身 vs 读数）")
        self.assertEqual(-300.0, self.bw.FAST_THR, u"预登记的快档阈值是 -300")
        self.assertEqual(-150.0, self.bw.MILD_THR, u"预登记的慢档阈值是 -150")

    def test_recent_returns_last_k(self):
        """读数端的取数口径：**各自最近 k 房**。"""
        old = self.bw.AR.rooms_for
        self.bw.AR.rooms_for = lambda st, since: [{"net": i} for i in range(1, 8)]
        try:
            self.assertEqual([5, 6, 7], self.bw.recent("x", "T", 3))
            self.assertEqual([1, 2, 3, 4, 5, 6, 7], self.bw.recent("x", "T", 99))
        finally:
            self.bw.AR.rooms_for = old

    def test_driver_uses_last_k_of_each_arm(self):
        """★ 枚举证据：最老一房放个大偏差 —— 若真的“只看最近 k 房”，它必须被排除。"""
        old = self.drv.arm_recent
        # 最老一房巨亏：若判据误用“全窗口”就会触发熔断；只看**最近 6 房**则不会。
        cand = [-9999.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        base = [0.0] * 7
        self.drv.arm_recent = lambda st, since, k: (cand if st == "c" else base)
        try:
            abort, m, n, bm = self.drv.guard_candidate("c", "b", "T")
        finally:
            self.drv.arm_recent = old
        self.assertFalse(abort, u"判据只能用各自最近 6 房（满 7 房平均值 -1428 会误触发）")
        self.assertEqual(7, n, u"返回的房数是 min(len)（展示口径）")
        self.assertLess(m, -1000.0, u"展示口径确实是全 n 房均值（与判据的最近 k 不同口径）")


if __name__ == "__main__":
    unittest.main()
