# -*- coding: utf-8 -*-
"""`tools/ab_ctl.py::start()` 的 **E002 护栏**单测：已有 `_ab_driver` 在跑时拒绝启动新战役。

真实场景：池子实验的驱动还在跑（房中对局），若直接 `ab_ctl.py start …`（旧实现会覆盖 `.ab_mode` 再拉一个驱动）
⇒ 两个驱动都按新配置排批 ⇒ 同账号两房并发 = E002。护栏要求先 `stop`（等驱动自然退出）。
安全：`.ab_mode` 路径换 tempfile；`_procs` 换成假函数；**绝不触碰真实 var/.ab_mode**。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ctl = _load("ab_ctl_start_t", "tools/ab_ctl.py")


_REAL_AB = os.path.join(ROOT, "var", ".ab_mode")


def _sentinel_snapshot():
    """返回真实哨兵内容；不存在返回 None（暂停期/正式赛模式都应允许）。"""
    try:
        with open(_REAL_AB, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


_REAL_AB_BEFORE = _sentinel_snapshot()


class TestStartE002Guard(unittest.TestCase):
    def test_refuses_when_driver_running(self):
        old = ctl._procs
        ctl._procs = lambda name: ([12345] if name == "_ab_driver.py" else [])
        try:
            rc = ctl.start(["speedtugc", "speedc152"], 1, ["speedc152"], force=False)
        finally:
            ctl._procs = old
        self.assertEqual(rc, 2, "已有驱动在跑时必须拒绝启动并返回非零")

    def test_real_sentinel_untouched(self):
        self.assertEqual(_sentinel_snapshot(), _REAL_AB_BEFORE,
                         "测试不得改变真实 A/B 哨兵的内容或存在性")


if __name__ == "__main__":
    unittest.main()
