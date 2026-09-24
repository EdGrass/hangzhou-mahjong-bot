# -*- coding: utf-8 -*-
"""SpeedValueBCV —— **BC 排序 + 爆头可达性 V**（顺序组合：V 先进基线选择，BC 再按自己的 margin 覆盖）。

## 为什么需要"叠加臂"（§V.45 / R1261）

- `speedvaluebc`（役 3 候选）改动 16.3% 的出牌决策；
- `speedvaluebaotouv5`（现役候选）改动 13.9%；
- 两者**只重叠 13.9%**（都改时仅 30.9% 选同一张牌）⇒ **并集 28.2%** ⇒ 两注几乎独立。

**关键动机（re-basing 规则）**：本项目纪律是"候选必须挂在上役采用的基线之上"。
若**役 3 采用 `speedvaluebc`**，则"役 4 的 V 轴"就**不能**再用挂 `speedvalue` 的 `speedvaluebaotouv5`
（那是复合臂）⇒ 役 4 的正确形态就是**本臂**（在 `speedvaluebc` 上再加 V）。
若役 3 未采用，则用现成的 `speedvaluebaotouv5`。

## 组合语义（刻意选"顺序组合"，避免两套尺度硬相加）

`value_of` 是 `SpeedValue._pick_discard` 的打分函数 ⇒ 本类**只覆盖 `value_of`**，即：
1. **V 先生效**：基线那一手在最小向听组内按 `SpeedValue.value_of + W_TILES × W_UKEIRE[s] × V` 选出；
2. **BC 再覆盖**：`SpeedValueBC._bc_pick` 仍在它的域内（同最小向听组、`base` 在组内、`max_candidates=4`）
   按 BC 网打分，**只在严格超过 `margin` 时**替换。
⇒ 两套分数量纲（V 的"活牌当量"与 BC 网的输出）**不相加**，各自在自己的尺度上决策，
  语义明确、可测（足迹/方向都能独立核对）。

其余（胡 / 自杠 / 抓打圈 / 副露窗口 / 兜底）全部沿用 `SpeedValueBC`，**一字不改**。
"""
from __future__ import annotations

from .baotou_value import value as _V
from .speedvalue import SpeedValue
from .speedvaluebc import SpeedValueBC


class SpeedValueBCV(SpeedValueBC):
    W_TILES = 5.0                 # 与 speedvaluebaotouv5 同剂量（该剂量在 5/10/20 已饱和）

    def __init__(self, name="speedvaluebcv", **kw):
        super().__init__(name=name, **kw)

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
