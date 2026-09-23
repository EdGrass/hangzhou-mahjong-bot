# -*- coding: utf-8 -*-
"""SpeedC154 —— **庄位条件化**：做庄时**不弃胡换爆头**（其余 100% 继承 speedc151）。

动机（2026-09-16，基于已修正的门户口径）：
- 缺口价值预算里**庄胡收入 = 67% 的缺口**（§9.16：+85 分/房），庄胡率我们 26.3% vs 强手 32.1%；
  而 §9.29 是**用分解**（不是实验）得出结论"不存在庄位专用打法"，据此关掉了这个方向；
- 赔付结构上，庄位的**下行不对称**：做庄时对手自摸我们要付 **8m**，做闲时多数情况只付 **1m**；
  赢下的价值统一 ×2.4（24m vs 10m，均匀放大 ⇒ 对"速度 vs 番数"的相对取舍是中性的），
  但**下行**不是均匀放大的 ⇒ **做庄时"锁定现成的一胡 + 连庄"比"拿它去赌爆头升级"更划算**；
- 我们的策略是启发式的（不是赔付 EV 最优）⇒ 它**没有按座位区分**，所以"座位条件化"是**未测过的单变量**。

本臂与 `speedc151` 的**唯一差别**：`_best_giveup()` 在**自己是庄**时返回 `None`
⇒ 有可胡的牌就直接胡；**做闲时 100% 保持 c151/C036 原样**（守住项目红线：不牺牲 C036 的收益）。

预期（**先写下来，避免事后解释**）：
- 庄胡率 ↑（主端点）、番/胡 略 ↓、**非庄位行为逐位不变**；
- 判据仍是 `tools/ab_readout.py` 的净胜/房（150 房/臂，t≥1.5 才采用）。
"""
from __future__ import annotations

from .speedc151 import SpeedC151


class SpeedC154(SpeedC151):

    def __init__(self, name="speedc154"):
        super().__init__(name)

    def decide(self, view):
        # 先记下"这一手我是不是庄"（view 里的 dealer 由 bot/game.py 逐局注入；未知 ⇒ 按闲处理）
        try:
            d = view.get("dealer")
            self._is_dealer_now = bool(isinstance(d, int) and d == view.get("seat"))
        except Exception:
            self._is_dealer_now = False
        return super().decide(view)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        """做庄 ⇒ 不弃胡（返回 None ⇒ 上层直接胡）；做闲 ⇒ 走 C036 原判据。"""
        if getattr(self, "_is_dealer_now", False):
            return None
        return super()._best_giveup(hand, exposed, gangs, fan_now, chain)
