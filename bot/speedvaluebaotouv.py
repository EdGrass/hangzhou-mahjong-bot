# -*- coding: utf-8 -*-
"""SpeedValueBaotouV —— `SpeedValue` + **爆头可达性值函数 V** 的加权项（把 V 当"主项"而非并列项）。

## 为什么是这条轴（而且为什么它不是"已判死的爆头专用规则"）

§V.36 的同席对账显示我们的分差**一半在"赢分大小"**：
`赢分 +4.44 vs top32 +5.28`、**番/胡 1.31 vs 1.42**、**爆头/胡 22.5% vs 28.7%**、杠开/胡 1.16% vs 1.83%。
把 `分/轮` 拆成 `胡率 × 赢分/胡`：缺口 −0.84 ＝ **胡率贡献 −0.39 ＋ 赢分大小贡献 −0.45**
⇒ **"赢得大"这一半，现有四个排队臂（BC / 副露 / 排序器 / 纯进张）一个都不打**。

而 §V.38 判死的三个"爆头专用规则"都是**手写启发式**：
`GOD_MELD=False`（0.2%，且不改打白）、弃牌分里的爆头路径项（0.3~0.4%）、`speedbaotoucomplete`（**0.08%**）。
它们的共同点是：**没有把"爆头可达性"做成一个有分辨力的数值**。

`bot/baotou_value.py` 里有**拟合**出来的可达性值函数 V（R559：**局级 AUC 0.771**、分位极差 12×），
`bot/speedc207.py` 已证明把它当**加权主项**（而不是并列项）时作用面很宽（对 `speedvalue` 实测 **17.3%**）。
本文件把那套机制**移植到现役基线 `SpeedValue` 之上**（`speedc207` 是 `SpeedTUGC` 族底 ⇒ 直接对照是复合臂，不能排役）：

## 契约（相对 `speedvalue` 只多一条变量）

- **只覆盖 `value_of`**：在 `SpeedValue.value_of(...)` 之上加 `W_TILES × W_UKEIRE[s] × V(post-discard 状态)`；
- `_pick_discard` / 胡 / 杠 / 抓打圈 / 索取门控**全部沿用 `SpeedValue`**（一字不改）；
- V 的权重按**"等价多少张活牌"**表达（`W_TILES`），再乘 `SpeedValue.W_UKEIRE[s]` 折算成本模型的点数口径
  （避免把 c207 的 `u1` 口径混进 V 的点数口径）；
- V 算不出（模型缺失/异常）⇒ **不加分**（退化为纯 `SpeedValue`，零行为变化）。

⚠ 风险（写死）：V 是"该局以爆头胡"的预测器 —— 追爆头可能**换掉和牌速度**。
   因此本臂的判词必须同时看 **胡率** 与 **番/胡**（§V.36 的两半），不能只看番。
"""
from __future__ import annotations

from .baotou_value import value as _V
from .speedvalue import SpeedValue


class _BaotouVBase(SpeedValue):
    W_TILES = 0.0            # 等价活牌张数（越大越偏"追爆头"）

    def value_of(self, rem, e, g, vis, view, sh):
        v = SpeedValue.value_of(self, rem, e, g, vis, view, sh)
        if v is None or not self.W_TILES:
            return v
        try:
            view = view or {}
            god = view.get("god") or {}
            river = view.get("river") or []
            all_melds = view.get("all_melds") or []
            draw_idx = int(view.get("draw_idx") or 0)
            bv = float(_V(list(rem), e, g, river, all_melds, god, draw_idx, vis=vis))
        except Exception:
            return v
        w = float(getattr(self, "W_UKEIRE", {}).get(sh, 0.02))
        return v + self.W_TILES * w * bv


class SpeedValueBaotouV5(_BaotouVBase):
    W_TILES = 5.0

    def __init__(self, name="speedvaluebaotouv5"):
        super().__init__(name)


class SpeedValueBaotouV10(_BaotouVBase):
    W_TILES = 10.0

    def __init__(self, name="speedvaluebaotouv10"):
        super().__init__(name)


class SpeedValueBaotouV20(_BaotouVBase):
    W_TILES = 20.0

    def __init__(self, name="speedvaluebaotouv20"):
        super().__init__(name)
