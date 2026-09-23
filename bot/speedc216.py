# -*- coding: utf-8 -*-
"""SpeedC216 —— `c211` 的**单变量**候选：**落后时降低"弃胡求爆头"的门槛**。

动机（R592/R593/R625）：
- 差距的大头是**竞争效应**（强对手档我们 −73 分/房，top32 +37），量级 **110 分/房**；
- R625 算出 **+5~10 分/房量级的改动在一个月内判不出来** ⇒ **只有大改动值得做**；
- R595 否掉了"以副露为载体的对手自适应"，但**没试过以"爆头判据"为载体**。

做法（唯一差别）：
- 在 `decide(view)` 里缓存 `view["scores"]`（`bot/model.py` 已把服务器权威分数放进 view）；
- 当**我方分数落后本房最高分 ≥ `LAG`** 时，把 `p_conv` 从 0.71 降到 `P_LOW`（更愿意弃胡求爆头）；
- 其余 100% 继承 c211。

依据：落后时需要的是**大分翻盘**（爆头 fan 2→4 的价值远超平胡），
而 C036 原本的 0.71 是"长期期望最优"，不是"落后时的最优"。
⚠ 先测 footprint（分歧率，R545：<10% 视为没跑到）。
"""
from __future__ import annotations

from .speedc211 import SpeedC211


LAG = 100.0        # 落后本房最高分多少算"需要翻盘"
P_LOW = 0.55       # 落后时的转化率阈值（默认 0.71）


class SpeedC216(SpeedC211):
    def __init__(self, name="speedc216", lag=LAG, p_low=P_LOW):
        super().__init__(name)
        self.LAG = float(lag)
        self.P_LOW = float(p_low)
        self._base_p = float(getattr(self, "p_conv", 0.71) or 0.71)
        self._scores = None

    def _lagging(self):
        sc = self._scores
        if not sc or len(sc) != 4:
            return False
        me = getattr(self, "_seat", None)
        if me is None or not (0 <= me < 4):
            return False
        try:
            return (max(sc) - sc[me]) >= self.LAG
        except Exception:
            return False

    def decide(self, view):
        # 缓存分数与座位（view 由 bot/model.py 构造，scores 是服务器权威）
        try:
            self._scores = view.get("scores")
            self._seat = view.get("seat")
        except Exception:
            self._scores = None
        self.p_conv = self.P_LOW if self._lagging() else self._base_p
        return super().decide(view)
