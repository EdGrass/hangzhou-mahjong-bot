# -*- coding: utf-8 -*-
"""★ R1544：钉住 **`.ab_mode` 的写入/读取契约**。

为什么：R1542（`_bsegment.already_switched`）与 R1543（`_adopt_pair.ab_config`）都依赖
`.ab_mode` 的**键名**（`arms` / `a`+`b` / `bundles` / `started`），而这个契约之前**没有任何测试**：
若将来 `ab_ctl` 改了键名，`ab_config()` 会**静默返回空**（R1543 的保护静默失效）而没人会发现。
本文件把“**写入器产出的东西，读取器必须能读出来**”钉死。
"""
from __future__ import annotations
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "var"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class TestAbModeContract(unittest.TestCase):
    def setUp(self):
        self.ac = _load("abctl_t", "tools/ab_ctl.py")
        self.ap = _load("adopt_t", "var/_adopt_pair.py")
        self.bs = _load("bseg_t2", "var/_bsegment.py")
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)

    def _write(self, cfg):
        f = os.path.join(self.d.name, ".ab_mode")
        with io.open(f, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return f

    def test_two_arm_format_round_trips(self):
        """2 臂：`ab_ctl` 写 `a`/`b` + `bundles` ⇒ 两个读取器都必须认。"""
        cfg = self.ac.build_cfg(["speedvaluebc", "speedvaluebcmeldp45"], 1,
                                bundles=["speedvaluebc"], started="2026-09-29 03:00:00")
        f = self._write(cfg)
        self.assertEqual(("speedvaluebc", "speedvaluebcmeldp45"), self.ap.ab_config(f))
        started, arms, bundle = self.bs.read_ab(f)
        self.assertEqual("2026-09-29 03:00:00", started)
        self.assertEqual(["speedvaluebc", "speedvaluebcmeldp45"], arms)
        self.assertEqual("speedvaluebc", bundle)

    def test_three_arm_format_round_trips(self):
        """≥3 臂（役3 形状）：写 `arms` ⇒ 读取器也必须认。"""
        cfg = self.ac.build_cfg(["speedvalue", "speedvaluebc", "speedvaluebaotouv5"], 1,
                                bundles=["speedvalue"], started="2026-09-25 20:52:39")
        f = self._write(cfg)
        self.assertEqual(("speedvalue", "speedvaluebc,speedvaluebaotouv5"), self.ap.ab_config(f))
        started, arms, bundle = self.bs.read_ab(f)
        self.assertEqual("2026-09-25 20:52:39", started)
        self.assertEqual(3, len(arms))
        self.assertEqual("speedvalue", bundle)

    def test_bundles_is_always_written(self):
        """★ R1156 同类：`bundles` 必须**两种分支都写**（否则阈值会悄悄从 1.50 变 1.96）。"""
        for arms in (["a1", "a2"], ["a1", "a2", "a3"]):
            cfg = self.ac.build_cfg(arms, 1, bundles=["a1"], started="T")
            self.assertIn("bundles", cfg)
            self.assertEqual(["a1"], cfg["bundles"])


if __name__ == "__main__":
    unittest.main()
