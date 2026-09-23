# -*- coding: utf-8 -*-
"""SpeedC230 —— 单变量候选（副露轴）：**吃牌时只放行"最宽的那个搭子"**。

问题（R879 实测，最近 12 房 / 104 个 response_chi 窗口）：
    `SpeedTUGC.decide()` 的吃牌分支是
        for pair in _chi_pairs(hand, offer):
            if self._want_claim(view, "chi", pair): return chi
    ⇒ **取的是"第一个过门控的搭子"，不是"最优的搭子"**。
    实测：104 个吃牌窗口里 58 个至少有一个搭子过门控，其中 **13 个有 ≥2 个搭子可过**，
    而这 13 个里有 **5 个（38%）取到的不是最宽的**：
        offer=8w: 取 ['6w','7w'] 后 live **14**  vs 取 ['7w','9w'] 后 live **46**（3.3 倍）
        offer=8w: 79 vs 94 / 17 vs 27 / offer=6b: 63 vs 67

背景（R878，修正四家副露扣除后）：我们的 1 向听 live 随副露数**下降**（20.5→20.0→19.8），
顶级**不降**（22.6→22.4→22.7）；且我们 chi 占比 54.0% > 顶级 49.2%、杠只有他们 60%。
⇒ 副露轴的真问题不是"要不要副露"，而是"**副露之后手里留得够不够宽**"。

做法（**只改这一个钩子，不复制 decide()**）：
    `_want_claim(kind="chi", pair)` 先走父类门控（c151 = 严格/质量感知门控，语义不变）；
    若通过，则在**所有也能过父类门控的搭子**里按 `(向听, −真进张)` 选最优，
    **只对最优那个返回 True** ⇒ `decide()` 的"取第一个"自然等于"取最宽"。
    单搭子/非吃牌/形状不标准 ⇒ 原样返回父类结果（**严格 no-op**）。

成本：只在"≥2 个搭子都能过门控"时多算 1~2 次 `_after_best`（每次 1~3 次 real_ukeire）；
实测窗口数占比约 12%（13/104），故均值开销可忽略；M=10 门禁仍需按纪律跑。
"""
from __future__ import annotations

from .speed import _chi_pairs
from .speedc136 import _after_best
from .speedc151 import SpeedC151
from .ukeire import visible_counts


class SpeedC230(SpeedC151):
    def __init__(self, name="speedc230"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        if not super()._want_claim(view, kind, pair):
            return False
        if kind != "chi" or not pair:
            return True
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if not offer or len(hand) != 13 - 3 * e - g:
            return True                      # 形状不标准 ⇒ 不改行为
        pairs = _chi_pairs(hand, offer)
        if len(pairs) < 2:
            return True                      # 只有一个搭子 ⇒ 无选择余地
        vis = visible_counts(hand, river=view.get("river"),
                             all_melds=view.get("all_melds"))
        best = None
        for p in pairs:
            if not super()._want_claim(view, "chi", p):
                continue
            aft = _after_best(hand, offer, "chi", p, e, g, vis, self.GOD_MELD)
            if aft is None:
                key = (99, 0.0)
            else:
                key = (aft[0], -(aft[1] or 0.0))
            if best is None or key < best[0]:
                best = (key, tuple(p))
        if best is None:
            return False                     # 不可达（本 pair 已过父类门控）
        return tuple(pair) == best[1]
