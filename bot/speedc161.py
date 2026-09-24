# -*- coding: utf-8 -*-
"""SpeedC161 —— **c156 + 「接第二/第三摊」**（单变量：只再加一条副露门控）。

**依据（2026-09-17 新实测，`var/_strong_meld_vs_gate.py --games 400 --policy speedc156`）**：
对强者实际完成的吃/碰 5,067 次，问 c156 门控要不要 ⇒ **会要 91.5% / 不要 8.5%（430 次）**。
把被拒那 430 次与外面对照，残差有**明确结构**：

| 画像 | 我方也会要（4,637） | **我方不要（430）** |
|---|---|---|
| ukeire 变化 | −5.40 | **−8.16** |
| 含白比例 | 0.39 | 0.62 |
| 巡目 | 4.47 | **7.31** |
| **已有副露摊数** | **0.44** | **0.76** |
| 摊数分布 | 0 摊 63.9% / 1 摊 29.0% / ≥2 摊 7.1% | **0 摊 41.9% / 1 摊 41.2% / ≥2 摊 17.0%** |

⇒ **我们抵制的不是"开局副露"，而是"已经开了口之后继续吃/碰（第 2、第 3 摊）"**：
被拒的里面 **58.1% 手上已经有 ≥1 摊**（对照组只有 36.1%），"≥2 摊"占比是 2.4 倍。
机制上也自洽：**爆头 = 4 面子 + 白孤**，副露是**最快做满 4 面子**的通道；而"真进张/向听"这套指标
在**已经副露的爆头路线**上会低估"把第 2/3 摊做出来"的价值。

**规则（单向增加，绝不否决 c156/基线的任何索取）**：c156 说"不要"的窗口上，若
  ① 已有副露摊数 ≥ `min_melds`（默认 1 —— 直击残差）
  ② 牌河长度 ≥ `min_river`（默认 16；被拒组巡目均值 7.31）
  ③ 吃/碰**不吃掉白**（`require_bai_keep`，默认 True：白是爆头/四白的票）
  ④ 吃/碰后向听不变差
  ⑤ 真进张损失 ≤ `max_loss`（默认 12；被拒组均值 −8.16）
⇒ 则接受。

判据（与队列一致）：机制（有副露局占比 / 8 巡听牌 / 番 / 爆头）+ `tools/ab_readout.py` 净胜/房（150 房/臂、t≥1.5）。
**离线预筛口径**：门控工具上"我们也会要 = 强者实际副露的比例"必须**明显高于 91.5%**，否则不值得占臂位。
"""
from __future__ import annotations

import os

from .speed import _chi_pairs
from .speedc136 import _after_best, _state
from .speedc156 import DEFAULT_MELD, SpeedC156
from .ukeire import visible_counts

BAI = "白"


def _env_float(name, dflt):
    try:
        return float(os.environ.get(name, dflt))
    except Exception:
        return float(dflt)


class SpeedC161(SpeedC156):

    def __init__(self, name="speedc161", claim_p=0.60, meld_path=DEFAULT_MELD,
                 min_melds=None, min_river=None, max_loss=None, require_bai_keep=None):
        super().__init__(name, claim_p=claim_p, meld_path=meld_path)
        # 参数可用环境变量覆盖（**只用于离线预筛探针**；生产用默认值）
        self.min_melds = int(min_melds if min_melds is not None else _env_float("C161_MIN_MELDS", 1))
        self.min_river = int(min_river if min_river is not None else _env_float("C161_MIN_RIVER", 16))
        self.max_loss = float(max_loss if max_loss is not None else _env_float("C161_MAX_LOSS", 12))
        self.require_bai_keep = bool(require_bai_keep if require_bai_keep is not None
                                     else int(_env_float("C161_BAI_KEEP", 1)))

    def _want_claim(self, view, kind, pair=None):
        if super()._want_claim(view, kind, pair):
            return True                      # c156（含学习网）已要 ⇒ 直接要（不否决任何索取）
        try:
            offer = view.get("offer_tile")
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            if not offer or len(melds) < self.min_melds:
                return False                 # ① 只补"已经开口"的摊位
            rl = view.get("river_len")
            if rl is None:
                rl = len(view.get("river") or [])
            if int(rl) < self.min_river:
                return False                 # ② 中盘偏晚
            e = len(melds)
            g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
            if len(hand) != 13 - 3 * e - g:
                return False
            vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            before = _state(hand, e, g, vis, self.GOD_MELD)
            if before is None or before[1] is None:
                return False
            if kind == "chi":
                opts = [("chi", p) for p in _chi_pairs(hand, offer)]
            else:
                opts = [(kind, None)]
            for k, p in opts:
                used = list(p) if k == "chi" else [offer, offer]
                if self.require_bai_keep and BAI in used:
                    continue                 # ③ 不把白吃/碰出去
                after = _after_best(hand, offer, k, p, e, g, vis, self.GOD_MELD)
                if after is None or after[1] is None:
                    continue
                if after[0] > before[0]:
                    continue                 # ④ 向听不变差
                if after[1] < before[1] - self.max_loss:
                    continue                 # ⑤ 进张损失有界
                return True
            return False
        except Exception:
            return False
