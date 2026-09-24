# -*- coding: utf-8 -*-
"""SpeedC159C —— 早期**反向**档：前 3 巡给**负**权重（偏好保对子），中盘 1.0、末盘 1.5。

依据（STATUS §9.77 真机证据，5 房/臂门户口径）：
  c151 逐巡拆对率 T1..T8 = 9.0/5.8/7.1/9.7/7.6/15.2/14.1/10.7%
  强者            = 2.3/2.5/4.2/6.5/8.6/10.1/11.4/11.8%
  ⇒ T1 是强者的 ~4 倍；而 c159（早盘权重 0）只能退回基线的 5.2%，**仍高于 2.3%**
  ⇒ 要贴近强者曲线，早盘需要**负权重**（= 早期更愿意保留对子）。
注意：中末盘**不加力**（真机显示 c151 的 T6/T7 已经高于强者；`speedc159b` 的"中末加力"前提因此被推翻，见 §9.78）。
"""
from __future__ import annotations

from .speedc159 import SpeedC159

W_EARLY_NEG = (-0.3, 1.0, 1.5)


class SpeedC159C(SpeedC159):

    WEIGHTS = W_EARLY_NEG

    def __init__(self, name="speedc159c"):
        super().__init__(name, weights=W_EARLY_NEG)
