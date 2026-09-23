# -*- coding: utf-8 -*-
"""`speedgiveup` —— c151 的**单结构旋钮**：弃胡换爆头时要求更大的期望余量。

现状（`bot/speedtug.py:73` / `bot/speedc141.py:61`）：
    能胡则先看 `_best_giveup`：若 `p_conv * best_fan > fan_now` 就**弃胡**去打爆头形。
问题（c219/R667 已量化）：
- 该判据**在真实语料上饱和**：爆头番/现在番 ≥ 2.0 占 **97.7%**，而 `p_conv=0.71`
  ⇒ `0.71 × 2.0 = 1.42 > 1` ⇒ **几乎每个窗口都触发**；`p_conv` 在 (0.5, 1) 内怎么调都**逐字相同**；
- 而 `p_conv = 0.71` 的来源是**极小样本**（`speedtug.py` 自述：真机 7 样本 5 中）；
- ⇒ 实际行为 = "**只要存在爆头线路就弃胡**"，这个赌注是靠 7 个样本定的。

本臂（**非饱和**结构旋钮，不是调阈值）：
    把判据改成 `p_conv * best_fan > MARGIN * fan_now`
  - `MARGIN = 1.0` ⇒ 与现状**逐位等价**（保真基线）；
  - `MARGIN = 2.0` ⇒ 要求"爆头线路的期望番 ≥ 现在胡的 2 倍"才弃胡（≈要求番比 ≥ 2.82）⇒ **不再饱和**。

方向护栏（可测、单向）：**MARGIN 越大 ⇒ 越少弃胡**；即新臂每一次弃胡都必须对应现状也弃胡
（不可能出现"现状不弃、新臂弃"）。

⚠ 唯一实现代价：`_best_giveup` 的选牌段必须复制（父类只返回"牌/None"，拿不到 `best_fan`
用于换判据）。与 `speedc141` 的差别**只有末行判据**。
"""
from __future__ import annotations

from mahjong.hu import is_baotou
from mahjong.tiles import GOD_TILE

from .speedc151 import SpeedC151


class _GiveupBase(SpeedC151):
    MARGIN = 1.0          # 1.0 = 与现状逐位等价

    def __init__(self, name="speedgiveup"):
        super().__init__(name)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        """C141 的选牌逻辑 + **可调的期望余量**（末行与现状的唯一差别）。"""
        chain = chain or {"count": 0, "piao": 0}
        best, best_fan = None, None
        for d in sorted(set(hand)):
            after = list(hand)
            after.remove(d)
            try:
                if not is_baotou(after, allow_qidui=(exposed == 0 and gangs == 0),
                                 exposed_melds=exposed, gangs=gangs):
                    continue
            except ValueError:
                continue
            c2 = chain
            if d == GOD_TILE:            # 财飘：爆头态弃白 ⇒ 链 +1（再 ×2）
                c2 = {"count": int(chain.get("count") or 0) + 1,
                      "piao": int(chain.get("piao") or 0) + 1}
            fb = self._baotou_fan(after, exposed, gangs, c2)
            if fb is None:
                continue
            if best_fan is None or fb > best_fan:
                best, best_fan = d, fb
        if best is None:
            return None
        return best if self.p_conv * best_fan > self.MARGIN * fan_now else None


class SpeedGiveupM1(_GiveupBase):
    """保真臂：MARGIN=1.0 ⇒ 必须与 c151 逐位相同（用于证明复制无偏差）。"""
    MARGIN = 1.0

    def __init__(self, name="speedgiveupm1"):
        super().__init__(name)


class SpeedGiveupM2(_GiveupBase):
    """候选：要求爆头线路期望番 ≥ 现在胡的 2 倍才弃胡（非饱和）。"""
    MARGIN = 2.0

    def __init__(self, name="speedgiveupm2"):
        super().__init__(name)
