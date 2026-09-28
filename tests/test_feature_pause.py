# -*- coding: utf-8 -*-
"""平台能力暂停模式回归：match_enabled=false 时冻结训练，恢复后自动解除。"""
import importlib.util
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "var") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "var"))

import _feature_mode as fm


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class TestFeaturePause(unittest.TestCase):
    def test_no_flag_never_pauses(self):
        old = fm.PAUSE_FLAG
        try:
            fm.PAUSE_FLAG = os.path.join(tempfile.gettempdir(), "no_such_pause_flag")
            fm.feature_match_enabled = lambda: False
            self.assertFalse(fm.handle_pause_on_startup())
        finally:
            fm.PAUSE_FLAG = old

    def test_flag_stays_while_match_disabled(self):
        fd, p = tempfile.mkstemp(prefix="pause_")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        old = fm.PAUSE_FLAG
        try:
            fm.PAUSE_FLAG = p
            fm.feature_match_enabled = lambda: False
            self.assertTrue(fm.handle_pause_on_startup())
            self.assertTrue(os.path.exists(p))
        finally:
            fm.PAUSE_FLAG = old

    def test_flag_clears_when_match_enabled(self):
        fd, p = tempfile.mkstemp(prefix="pause_")
        os.close(fd)
        old = fm.PAUSE_FLAG
        try:
            fm.PAUSE_FLAG = p
            fm.feature_match_enabled = lambda: True
            self.assertFalse(fm.handle_pause_on_startup())
            self.assertFalse(os.path.exists(p))
        finally:
            fm.PAUSE_FLAG = old

    def test_bsegment_transition_flag_round_trip_and_stale(self):
        """R1592：B 段换役让位标记必须能设/清，且崩溃残留会自动过期。"""
        with tempfile.TemporaryDirectory() as d:
            old_flag = fm.BSEG_WAIT_FLAG
            old_stale = fm.BSEG_WAIT_STALE_SEC
            try:
                fm.BSEG_WAIT_FLAG = os.path.join(d, ".bsegment_waiting")
                fm.BSEG_WAIT_STALE_SEC = 60
                fm.set_bsegment_waiting(True)
                self.assertTrue(fm.bsegment_waiting())
                fm.set_bsegment_waiting(False)
                self.assertFalse(fm.bsegment_waiting())
                fm.set_bsegment_waiting(True)
                young = time.time() - 30
                os.utime(fm.BSEG_WAIT_FLAG, (young, young))
                self.assertTrue(fm.bsegment_waiting())
                old = time.time() - 61
                os.utime(fm.BSEG_WAIT_FLAG, (old, old))
                self.assertFalse(fm.bsegment_waiting())
                self.assertFalse(os.path.exists(fm.BSEG_WAIT_FLAG))
            finally:
                fm.BSEG_WAIT_FLAG = old_flag
                fm.BSEG_WAIT_STALE_SEC = old_stale

    def test_self_healing_scripts_wire_the_gate(self):
        for rel in ("var/_ensure_all.py", "var/_watchdog.py", "var/_keeper.py", "var/_ab_driver.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                s = fh.read()
            self.assertIn("_feature_mode", s, rel)
            self.assertTrue(("pause_requested" in s) or ("handle_pause_on_startup" in s), rel)


if __name__ == "__main__":
    unittest.main()
