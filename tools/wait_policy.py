# -*- coding: utf-8 -*-
"""把"等待入席窗口"的**配置读取**抽成安全模块（可 import、无副作用），供 keeper 与测试共用。

⚠ 为什么必须抽出来：`var/_keeper.py` 在**模块级调用 main()**（import 即起守夜）⇒ 单测不能直接 import 它
（既有 `tests/test_keeper_yield.py` 就是**只读源码文本**来规避这一点）。所以配置逻辑放这里，脚本 import 本模块。
"""
from __future__ import annotations
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT_CFG = os.path.join(ROOT, "var", ".wait_until_second")


def wait_args(cfg_path=None):
    """若 `var/.wait_until_second` 存在且是 0~59 的整数 ⇒ 返回 `["--wait-until-second", N]`，否则 []。

    这是"入席秒 ↔ 同桌强度"实验（STATUS §9.87/§9.90）**成立后的全局启用开关**：
    放这个文件 ⇒ keeper 的每个批次都会等到该秒入席；删掉即恢复默认行为。
    """
    path = cfg_path or WAIT_CFG
    try:
        v = int(io.open(path, encoding="utf-8").read().strip())
    except Exception:
        return []
    return ["--wait-until-second", str(v)] if 0 <= v <= 59 else []
