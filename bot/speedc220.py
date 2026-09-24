# -*- coding: utf-8 -*-
"""❌ **已否决（R694，2026-09-20）**：权威口径 `tools/offline_replay.py` 实测分歧率仅 **2.4%**（502/21,212）< 10% 门禁。`r`n两难：要 footprint ≥10% 必须考察全部保持听牌的候选（8~14 次 `waits()`）⇒ **M=10 破 3s**（p99 1,930ms）；`r`n要过 M=10 只能考察 2~3 个 ⇒ footprint 只有 2.4%。**没有同时满足的配置** ⇒ 不排期。以下为历史记录：`r`n`r`n✅ **曾以为通过候选四问（R693）**（后经 R694 权威口径复核否决）：`r`n① 方向对（自摸 2.4 倍 + 按牌自摸率差异巨大）；② **footprint 19.8%**（547/2,767 个"弃后仍听牌"决策）；`r`n③ **M=10 通过**：draw p99 **574.8ms** / max **1,075ms** / 超 3s=**0**（基线同条件 405/1052）；window p99 1.3ms / max 125ms；`r`n④ 量级 ≈20 分/房 量级（⚠ 上界式估算，见下）。`r`n★ 通过 M=10 的关键：**候选枚举砍到 `MAX_CAND=1`**（只考察"弃掉最低价值牌"这一种替代）⇒ `waits()` 从 8~14 次降到 **2 次**。`r`n   （全枚举版本实测 p99 1,930ms / max 3,796ms ⇒ 被延迟否决；砍到 1 后才过。）`r`n
SpeedC220 —— **等张"期望分值"取舍**（并列项，向听主键不动）。

## 来路（本会话 2026-09-20 的证据链，每一步都自证过）

- **R678**（完整 P&L，3,200 block）：我们对 top32 差 **−84 分/房**，其中 **赢的频率占 60%**；
- **R679**（按"赢的那张牌"分层）：自摸差距一分为二 —— **组成效应 ≈1.6pp（可攻）** +
  同牌种残差 ≈1.5pp（对手怎么对待我们，自身决策修不了）；
- **R672**：12 个臂**都没有动过自摸占比**（所以需要新旋钮）；
- **R688**（footprint 实测，150 文件）：在我们 **2,767 个"弃后仍听牌"的决策**里，
  **56.4% 存在并列候选**（≥2 种弃法都保持听牌），其中 **33.2% 存在"期望分值更高"的等张**
  （中位提升 **+1.67 分/胡**，均值 +1.92，最大 +7.23）⇒ **footprint 远超 10% 线**。

## 规则（唯一改动）

自摸的赔付是荣和的 **~2.4 倍**（实测 自摸 32.2 / 荣和 13.3），而**每张牌的自摸率差异巨大**
（R679 实测：`1t` 14.4%、`1w` 15.4% ↔ `3b` 34.6%、`5w` 32.7%）。于是：

    子分值 W = mean over 等张 t of [ P(自摸|t) × 32.2 + (1 − P(自摸|t)) × 13.3 ]
    在"弃哪张仍听牌"的并列取舍里，若存在 **W 比基线选择高出 ≥ MARGIN（0.5 分/胡）** 的弃法，
    则改选它；否则**完全按基线**。

**为什么下行有界**：这是**并列项** —— 只在**已听牌**的舍牌之间换张，**向听数、听牌张集合的"存在性"都不变**
（只换等张集合），不动主键、不动胡牌判据、不动副露闸门。

## 局限（必须随结论引用）

1. `P(自摸|t)` 是 R679 从历史**条件于"已和牌"**的样本估出的**观测值**，当因果权重用**有偏**
   （例如某些牌的自摸率高，可能是因为会等这些牌的人本来就少）；
2. 只按"每张牌的自摸率"取平均，**没有**按剩余张数加权（活等已在基线里）也没有对手状态；
3. 期望分值只用 `自摸 32.2 / 荣和 13.3` 两个均值，不区分番型（番型由别处决定）。

⇒ 因此它**必须走离线 footprint → 真机 A/B** 的正常流程，不能靠离线胜率自证。
"""
from __future__ import annotations

from mahjong.shanten import waits as _waits
from mahjong.shanten_exact import shanten as _exact_shanten

from .speedtugc import SpeedTUGC

# R679 实测的按牌自摸率（我方；单位 %）—— 未见过的牌用全局 25.8%
SD = {"白": 97.0, "1w": 15.4, "9b": 17.3, "9w": 18.3, "1t": 14.4, "2t": 25.0, "8w": 21.5,
      "9t": 17.1, "1b": 20.1, "2w": 20.2, "2b": 19.3, "3b": 34.6, "5w": 32.7, "3w": 25.3,
      "7w": 30.9, "3t": 31.9, "8t": 26.9, "8b": 24.0}
DEF = 25.8
TS_PTS = 32.2      # 自摸均分（实测）
RON_PTS = 13.3     # 荣和均分（实测）
MARGIN = 0.5       # 分/胡：低于此差不换（避免噪声驱动的手数抖动）
MAX_CAND = 3       # 每次决策最多评估的候选弃牌数。★ R693：砍到 1（只看"弃掉最低价值牌"）⇒ waits() 只调 2 次


def _tile_value(t):
    p = SD.get(t, DEF) / 100.0
    return p * TS_PTS + (1.0 - p) * RON_PTS


def wait_set_value(wait_tiles):
    """整套等张的期望分值（**集合加权平均** —— 不是集合里最好的那一张；
    两者差 300 倍，见 R688 的度量坑）。"""
    w = list(wait_tiles)
    if not w:
        return 0.0
    return sum(_tile_value(t) for t in w) / len(w)


class SpeedC220(SpeedTUGC):
    def __init__(self, name="speedc220", margin=MARGIN, max_cand=MAX_CAND):
        super().__init__(name)
        self.margin = float(margin)
        self.max_cand = int(max_cand)
        self.stats = {"dec": 0, "tp": 0, "switch": 0}

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):  # type: ignore[override]
        base = super()._pick_discard(hand, drawn, exposed, gangs, view)
        self.stats["dec"] += 1
        if not base or base not in hand or len(hand) < 14:
            return base
        # 只在**基线打法仍听牌**时才动（保证"向听主键不动"）
        def _w(h):
            try:
                return _waits(list(h), exposed_melds=exposed, gangs=gangs)
            except Exception:
                return []
        hb = list(hand)
        hb.remove(base)
        wb = _w(hb)
        if not wb:
            return base
        self.stats["tp"] += 1
        best_t, best_v = base, wait_set_value(wb)
        # ★ 延迟护栏（R689）：M=10 下 14 个候选的 waits() 会把 p99 推到 1.9s（超 3s 预算的 64%）。
        #   把候选枚举**硬限制**为 MAX_CAND 个（只影响"找更好的等张"这一并列项，不影响合法性）。
        # ★ R694 修正：原实现"按牌价值排序后取前 K 个"里**大多不保持听牌** ⇒ 逐个 `continue`
        #   ⇒ 真实分歧率只有 1.4%（权威口径 `offline_replay` 实测）。
        #   正确做法：**先用便宜的 `exact_shanten` 筛出"保持听牌"的候选**（约等于基线自己的工作量），
        #   **只对它们**按牌价值排序取前 K 个、再调 `waits()`（逐个 waits 才是贵的）。
        _q = (exposed == 0 and gangs == 0)
        tp = []
        for d in sorted(set(hand)):
            h2 = list(hand)
            h2.remove(d)
            try:
                if _exact_shanten(h2, qidui=_q, exposed_melds=exposed, gangs=gangs) == 0:
                    tp.append(d)
            except Exception:
                continue
        if not tp:
            return base
        tp.sort(key=lambda x: _tile_value(x))       # 先看"低价值牌"作为弃牌
        for d in tp[:self.max_cand]:
            h2 = list(hand)
            h2.remove(d)
            w2 = _w(h2)
            if not w2:
                continue                      # 不保持听牌 ⇒ 不是并列项，直接跳过
            v = wait_set_value(w2)
            if v > best_v + self.margin:
                best_t, best_v = d, v
        if best_t != base:
            self.stats["switch"] += 1
        return best_t
