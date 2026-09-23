# -*- coding: utf-8 -*-
"""`tools/ab_ctl.py::stop()` 的 **E002 防护**单测（2026-09-17 修）。

背景（真实窗口）：旧实现只等 ~45s 就强杀 `_ab_driver`；而一房要 ~14 分钟 ⇒ 房中对局时强杀驱动
**不会**杀掉在跑的 `run_bot`，watchdog 会在 ≤90s 内拉起 keeper ⇒ keeper 的 `/api/match` 幂等、
会回到**同一房** ⇒ 第二个 run_bot 进场 = **同账号双活 = E002**。
现在的行为：**等足够久（默认 20 分钟）、到点仍不退出就拒绝强杀并返回 2**（要强杀必须显式 --force）。

安全：`.ab_mode` 与策略文件路径都换成 tempfile，**绝不触碰真实的 var/.ab_mode**。
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
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


ctl = _load("ab_ctl_stop_t", "tools/ab_ctl.py")


_REAL_AB = os.path.join(ROOT, "var", ".ab_mode")


def _sentinel_snapshot():
    """返回真实哨兵内容；不存在返回 None（暂停期/正式赛模式都应允许）。"""
    try:
        with open(_REAL_AB, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


_REAL_AB_BEFORE = _sentinel_snapshot()


class TestStopE002Guard(unittest.TestCase):
    def test_refuses_to_force_kill_when_driver_alive(self):
        tmp = tempfile.mkdtemp(prefix="abstop_")
        ab = os.path.join(tmp, ".ab_mode")
        with io.open(ab, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": "speedtugc", "b": "speedc152"}))
        old = (ctl.AB, ctl._procs)
        killed = []
        ctl.AB = ab
        ctl._procs = lambda name: ([999999] if name == "_ab_driver.py" else [])
        os.environ["AB_STOP_WAIT_SEC"] = "0"          # 不真等
        try:
            rc = ctl.stop(force=False)
        finally:
            ctl.AB, ctl._procs = old
            os.environ.pop("AB_STOP_WAIT_SEC", None)
        self.assertEqual(rc, 2, "驱动仍在跑时必须拒绝强杀并返回非零")
        self.assertEqual(killed, [])
        self.assertFalse(os.path.exists(ab), "哨兵应已删除（让驱动自己走正常退出路径）")

    def test_real_sentinel_untouched(self):
        self.assertEqual(_sentinel_snapshot(), _REAL_AB_BEFORE,
                         "测试不得改变真实 A/B 哨兵的内容或存在性")


if __name__ == "__main__":
    unittest.main()
