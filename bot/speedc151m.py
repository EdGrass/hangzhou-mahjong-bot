# -*- coding: utf-8 -*-
"""SpeedC151M —— `speedc151` + **副露门控档位放宽**（单变量；**零档可证明是精确 no-op**）。

依据链（三条都是本项目自己的真机/同期证据）：
  ① **缺口在成型速度**（R811：`≤8 手听牌率` 46.2% vs 顶级 54.2% ⇒ **−8.0pp**；
     而"听牌活等张"13.37 **已高于**顶级 13.14 ⇒ 不是"听得窄"，是"成型慢"）；
  ② **副露是唯一的"直接成型"机制**，且**我们低于全场正常带**：
     全场目标带 `副露/局` **1.087~1.320**（journal L4269），
     我们：`speedtugc` 0.870（基线）→ `speedc151` **1.056（带边缘）** → 顶级 **1.223**；
  ③ **本项目唯一在成型轴为正的臂是 `speedc135`（+2.0pp）**（journal L11378~11390），
     而 `speedc211` 在成型轴 **−3.7pp（z=−3.9）** —— 放宽方向与缺口方向一致。

设计（为什么这是干净的单变量）：
  · `_want_claim` 先**原样**走 c151 自己的链（`super()` ⇒ C144 明杠 → C136 质量感知 → 严格）；
  · 仅在**原链说"不"**时，再看 `want_claim_tiered(mild_upto=K)`（复用 `bot/speedtugh.py` 的既有实现）；
  · ★ **`K=0` 时额外项恒不触发**：`want_claim_tiered(..., 0)` 在 `before>0` 上等价于严格门控，
    而严格门控已被 `super()` 覆盖 ⇒ **`c151m0` 与 `speedc151` 逐决策相同（可测试的硬契约）**；
  · `K` 越大 ⇒ 在 `向听 <= K` 时允许"等向听副露" ⇒ **副露率单调上升**（可标定到目标带）。

用法（标定副露率，Idle 优先级；不改 `run_bot.py`）：
    MILDS=0,1,2 MELD_MODULE=bot.speedc151m python -X utf8 var/_meld_calib.py --max-files=1200

⚠ 未注册进 `run_bot.STRATEGY_FACTORIES` ⇒ 对在途战役**惰性**。
"""
from __future__ import annotations

from .speedc151 import SpeedC151
from .speedtugh import want_claim_tiered

NAME = "c151m0"
GATE = 0


class SpeedC151M(SpeedC151):
    """`K=0` == `speedc151`（精确 no-op）；`K>0` 逐档放宽副露门控。"""

    MILD_UPTO = GATE

    def __init__(self, name=None, mild_upto=None, budget_ms=40.0):
        k = self.MILD_UPTO if mild_upto is None else int(mild_upto)
        super().__init__(name=name or ("c151m%d" % k), budget_ms=budget_ms)
        self.MILD_UPTO = k

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True
        if self.MILD_UPTO <= 0:
            return False
        return want_claim_tiered(view, kind, pair, mild_upto=self.MILD_UPTO)


def make(mild_upto=None):
    """构造指定档位的实例（给标定/回放工具用）。"""
    return SpeedC151M(mild_upto=mild_upto)