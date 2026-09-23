# -*- coding: utf-8 -*-
"""SpeedMeldTier —— **副露门控档位阶梯**（单变量：只动 `_want_claim`）。

动机（R805，2026-09-21；同房逐座位口径）：
  · 我们 副露/局 **0.878**、顶级 **1.182**、普通玩家 **1.026** ⇒ **我们比普通玩家还少副露**；
  · 历史结论（journal L682/L933/L4247/L4269）是"放宽副露 ⇒ 提听牌率但降番、净分负"，
    但那些实验用的是**粗放放宽**：C136 把副露/局推到 **1.499**，**越过了顶级水平**；
  · R804/R805 显示顶级是"**多副露 + 高番 + 高爆头**"⇒ 需要的是"**有选择的副露**"，
    即把副露率**标定到顶级水平（≈1.18）**，而不是一味放宽。

设计（为什么这是干净的单变量）：
  · `SpeedTUGC._want_claim` 是项目**预留的钩子**（源码注释："子类可换成'质量感知'版本"）；
  · 本模块**只换** `_want_claim`，实现直接复用**已有的** `bot/speedtugh.py:want_claim_tiered`
    （不新写判据）；
  · **`mild_upto=0` 与生产基线 `want_claim_strict_meld` 逐字等价**：
    两者只差 `allow_equal=(before <= mild_upto)`，而 `mild_upto=0 且 before>0` ⇒ `allow_equal=False`，
    恰好等于严格版；`before==0` 分支两者完全相同。
    ⇒ **阶梯的零档就是生产基线**，可用于验证"标定仪表本身没有偏差"；
  · `mild_upto` 越大 ⇒ 在 `向听 <= mild_upto` 时允许"等向听副露" ⇒ 副露率**单调上升**（可扫）。

用法（标定，不改 `run_bot.py`）：
    python -X utf8 var/_meld_calib.py --max-files=60

⚠ 本文件**未注册**进 `run_bot.STRATEGY_FACTORIES` ⇒ 对在途战役**惰性**。
"""
from __future__ import annotations

from .speedtugc import SpeedTUGC
from .speedtugh import want_claim_tiered


class SpeedMeldTier(SpeedTUGC):
    """`mild_upto` 档位副露门控；**0 == 生产基线（严格门控）**。"""

    MILD_UPTO = 0

    def __init__(self, name=None, mild_upto=None):
        k = self.MILD_UPTO if mild_upto is None else int(mild_upto)
        super().__init__(name or ("meldk%d" % k))
        self.MILD_UPTO = k

    def _want_claim(self, view, kind, pair=None):
        return want_claim_tiered(view, kind, pair, mild_upto=self.MILD_UPTO)


def make(mild_upto=None):
    """构造指定档位的实例（给标定/回放工具用）；`None`/省略 = 基线档。"""
    return SpeedMeldTier(mild_upto=mild_upto)