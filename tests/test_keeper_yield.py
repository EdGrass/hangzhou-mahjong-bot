# -*- coding: utf-8 -*-
"""keeper 让位单测：A/B 或正式赛模式在跑时，keeper **必须立刻停手**。

为什么重要（2026-09-17 实测）：keeper 过去不看 `.ab_mode`，于是 `ab_ctl start` 之后
它仍会把**已经起好的 4 房批次**跑完 ⇒ A/B 的第一房被推迟最长 ~2 小时（已发生两次）。
修法：在 keeper 主循环开头加哨兵检查，命中就删锁并 return。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    # 不要执行 main()（它在 __main__ 才跑），只读源码与常量
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        src = fh.read()
    return src


class TestKeeperYield(unittest.TestCase):
    def setUp(self):
        self.src = _load("kp", os.path.join("var", "_keeper.py"))

    def test_defines_both_sentinels(self):
        self.assertIn("AB_FLAG", self.src)
        self.assertIn(".ab_mode", self.src)
        self.assertIn("OFFICIAL_FLAG", self.src)
        self.assertIn(".official_mode", self.src)

    def test_loop_checks_sentinels_before_launching(self):
        """主循环里，哨兵检查必须出现在启动批次（subprocess.Popen）之前。"""
        i_flag = self.src.index("if os.path.exists(AB_FLAG) or os.path.exists(OFFICIAL_FLAG):")
        i_launch = self.src.index("subprocess.Popen(argv")
        self.assertLess(i_flag, i_launch, "哨兵检查必须在启动批次之前")
        # 命中后必须 return（而不是继续循环）
        seg = self.src[i_flag:i_flag + 400]
        self.assertIn("return", seg)

    def test_yield_message_mentions_driver(self):
        self.assertIn("_ab_driver", self.src)


if __name__ == "__main__":
    unittest.main()
