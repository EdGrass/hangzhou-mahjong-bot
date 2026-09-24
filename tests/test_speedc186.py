# -*- coding: utf-8 -*-
"""c186（c156 阈值校准版）单测。

锁两条：
① 阈值确实是 0.50，且**比 c156 更宽**（0.50 < 0.60 ⇒ 单向多要，绝不否决基线）；
② **单向超集纪律**：c151（家族母本）在任何窗口上接受的，c186 必须也接受
   —— 这是"只增不减、下行有界"的可执行定义。用真机 dec 窗口做夹具（有界抽样）。
"""
import collections
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bot.speedc151 import SpeedC151
from bot.speedc156 import SpeedC156
from bot.speedc186 import SpeedC186


class TestSpeedC186(unittest.TestCase):
    def test_threshold(self):
        self.assertAlmostEqual(SpeedC186().claim_p, 0.50)
        self.assertAlmostEqual(SpeedC156().claim_p, 0.60)
        self.assertLess(SpeedC186().claim_p, SpeedC156().claim_p)

    def test_one_way_superset_on_real_windows(self):
        from offline_replay import to_view, windows
        paths = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
        if not paths:
            self.skipTest("无 dec 语料")
        ws = [to_view(r) for r in windows(paths[-40:], limit_records=400)]
        self.assertGreater(len(ws), 0, "夹具为空")
        base, cand = SpeedC151(), SpeedC186()
        checked = 0
        for v in ws:
            try:
                ab = base.decide(v) or {}
            except Exception:
                continue
            if str(ab.get("action") or "pass") == "pass":
                continue
            checked += 1
            ac = cand.decide(v) or {}
            self.assertNotEqual(str(ac.get("action") or "pass"), "pass",
                                "c151 接受了但 c186 拒了（违反单向超集）：%s" % v.get("phase"))
        self.assertGreater(checked, 0, "样本里母本一次都没接受，夹具没覆盖到")

    def test_registered(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            self.assertIn("speedc186", fh.read())


if __name__ == "__main__":
    unittest.main()
