# -*- coding: utf-8 -*-
"""SpeedValueBCMeld —— **两层叠加的组合臂**：`SpeedValue` + BC 出牌排序 + 学习副露（R1228）。

## 为什么需要"组合臂"

到 10/7 还剩 ~5 个役位。单轴若各自只有小幅正效应，**真正的正分要靠叠加**。
本项目里两条**互不重叠**的层刚好可以叠（各自在预登记里都是单变量）：
- **出牌层**（`SpeedValueBC`，R1181）：在"弃后最小向听组"内用 154 维 BC 网络重排（draw 层 15.9%、中盘 18.0%）；
- **索取层**（`SpeedValueMeld`，R1190）：基线不要时用 81 维副露网补要（window 层，索取率 67.6%→74.7%，只加不减）。

⇒ 本臂 = 两层同时开，**相对 `speedvalue` 恰好两条变量**（按项目规范：组合臂判词用 `--bundles` 声明，
阈值走组合档 |t|≥1.50 —— 与单变量臂的 1.96 区别**必须显式传**，见 R1156）。

## 契约

- MRO：`SpeedValueBCMeld → SpeedValueBC → SpeedValueMeld → SpeedValue → SpeedC151 …`
  ⇒ `_pick_discard` 取 **BC 版**、`_want_claim` 取 **副露网版**，其余层 100% 沿用 `SpeedValue`；
- 初始化显式加载**两个模型**（`var/c073_orig_w2_net.pt` 与 `var/c121_meld_net.pt`），任一缺失 ⇒ 对应层自动退化为基线
  （即退化成单轴臂，而不是报错）；
- 与两个单轴臂各自的行为**可分别复核**：`--phase draw` 应等于 `speedvaluebc`、`--phase window` 应等于 `speedvaluemeld`。

## 起役前体检（两道）

    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluebcmeld --files 300 --phase draw   --lowprio
    python -X utf8 tools/offline_replay.py --base speedvalue --cand speedvaluebcmeld --files 300 --phase window --lowprio
"""
from __future__ import annotations

import collections
import os

from .c121meld import window_features
from .speedc121 import _MeldNet
from .speedc067 import _Net as _BCNet
from .speedvalue import SpeedValue
from .speedvaluebc import SpeedValueBC
from .speedvaluemeld import DEFAULT_MELD, SpeedValueMeld

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BC = os.path.join(ROOT, "var", "c073_orig_w2_net.pt")


class SpeedValueBCMeld(SpeedValueBC, SpeedValueMeld):
    """两层叠加：BC 出牌排序（`_pick_discard`）+ 学习副露（`_want_claim`）。"""

    def __init__(self, name="speedvaluebcmeld", model_path=None, margin=0.0,
                 max_candidates=4, shanten_lo=0, shanten_hi=2,
                 claim_p=0.60, meld_path=None):
        SpeedValue.__init__(self, name=name)          # 只初始化一次基类
        # --- 出牌层（与 SpeedValueBC 同参）---
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        self.shanten_range = (int(shanten_lo), int(shanten_hi))
        # ★ R1228 修：`SpeedValueBC._bc_pick` 会写 `self.stats`（used/changed/fallback）。
        #   缺这个属性会抛 AttributeError ⇒ 被上层兜底成 `_best_discard`（纯进张）
        #   ⇒ 臂会**静默变形**（实测足迹从 16% 变成 31%），务必初始化。
        self.stats = collections.Counter()
        try:
            self.model = _BCNet(model_path or DEFAULT_BC)
            self.model_path = model_path or DEFAULT_BC
        except Exception:
            self.model = None
            self.model_path = None
        # --- 索取层（与 SpeedValueMeld 同参）---
        self.claim_p = float(claim_p)
        try:
            self._mnet = _MeldNet(meld_path or DEFAULT_MELD)
        except Exception:
            self._mnet = None
