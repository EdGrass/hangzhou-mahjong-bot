# -*- coding: utf-8 -*-
"""`SpeedValueBaotouV10`（V 剂量档 10）的契约用例 —— R1371。

为什么单独一个文件：起役就绪门按 **`tests/test_<策略名>*.py`** 查单测
⇒ 内容已被 `test_speedvaluebaotouv5.py` 覆盖也不算数。本文件把该剂量档自己钉住
（剂量常量 / 单变量域 / 公式精确 / 模型异常回退 / 零剂量逐位一致 / 方向不变式）。
"""
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests._baotouv_dose import dose_case                      # noqa: E402
from bot.speedvaluebaotouv import SpeedValueBaotouV10            # noqa: E402


class TestSpeedValueBaotouV10(dose_case(SpeedValueBaotouV10, 10.0)):
    """该剂量档的契约（用例从共享工厂生成）。"""


if __name__ == "__main__":
    unittest.main()
