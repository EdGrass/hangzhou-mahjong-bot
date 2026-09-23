# -*- coding: utf-8 -*-
"""⚠⚠ **已作废，不要排期**（R667，2026-09-20 复核）——**本臂是空操作**：`_best_giveup` 的判据是`r`n`if self.p_conv * best_fan > fan_now`（**p_conv 越大才越容易弃胡**，本文档下面"降低门槛=更愿意弃胡"的写法**方向是反的**）；`r`n且 R655 实测番比分布：`爆头番/现在番 ≥ 2.0` 占 **97.7%** ⇒ **任何 `p>0.5` 都触发**，`0.55` 与 `0.71` 的`r`n触发集合**完全相同（259）** ⇒ **决策逐字相同**。保留代码仅为留档；若将来重开，必须换**非饱和旋钮**（改判据结构，不是调阈值）。`r`n
SpeedC219 —— `speedtugc` 上的**房内分差自适应**：落后时降低"弃胡求爆头"的门槛。

## 它解决什么问题

c216 提出过同一想法（落后时 `p_conv` 0.71 → 0.55），但**从未跑过任何真机/离线**，因为它的两个前提都不成立：

**① 基座错了。** c216 继承 `SpeedC211`，而 c211 已被真机 100 房证伪
（分/席局 −0.432 vs 基线 −0.188，z=2.35；R653 再加对手强度校正后 z=**−2.76**，更硬）。
在已知负收益的基座上做实验，即使新机制有效也被抵消 ⇒ 必须换到现役基线 `SpeedTUGC`。

**② "落后"的数据源错了（R654，2026-09-20 实测）。** c216 直接读 `view["scores"]` 并假设它是**房内累计局势**。
实测否掉：同一房的日志里 `本场积分` 出现 **10 次**、每次都是**零和向量**、量级 ±50~130，
而该房归档的房总分是 `[108, 90, 4, -202]`，**与最后一条快照 `[0, 88, -29, -59]` 不相等**
⇒ `scores` 是**逐单元（场/块）结算的增量**，不是房内累计。
c216 用 `max(sc) − sc[me] ≥ 100` 去判"房内落后"，量纲完全不匹配 ⇒ **触发条件错位**（这正是它零证据的真因）。

## 本臂的做法

- **自己累加**每次新出现的结算向量 ⇒ 得到房内局势 `room_scores`（对本作"逐局"还是"逐块"两种口径都成立，只要是增量）；
- `max(room_scores) − room_scores[me] ≥ LAG(100)` ⇒ 判为"落后需翻盘" ⇒ `p_conv = P_LOW(0.55)`，否则用基线 0.71；
- 其余 100% 继承 `SpeedTUGC`（含 C036 弃胡换爆头、严格副露闸门、C135 真进张）。

## 安全性（三条，都是"宁可退化也不要乱动"）

1. **观察不到 `scores` ⇒ 局势恒 0 ⇒ 永不触发 ⇒ 自动退化为基线行为**；
2. 累计越界（|x| > 3000）⇒ 判口径异常，清零重新累计（防静默错位累积）；
3. 自诊断计数：`n_dec`（总决策数）、`n_absorbed`（吸收了几次结算）、`n_lag`（判为落后的决策数）
   ⇒ **真机一跑就能验口径**：约 10 次/房 = 增量口径正确；≈1 次 = 平台给的是累计（需改）；
   `n_lag/n_dec` 同时就是 footprint（R545 纪律：<10% 视为"没跑到"）。

用法：`ROLLOUT_POLS=speedtugc,speedc219 python -X utf8 tools/offline_replay.py ...`
"""
from __future__ import annotations

from .speedtugc import SpeedTUGC

LAG = 100.0        # 落后本房最高分多少算"需要翻盘"
P_LOW = 0.55       # 落后时的转化率阈值（基线 0.71）
GUARD = 3000.0     # 累计异常保护


class SpeedC219(SpeedTUGC):
    def __init__(self, name="speedc219", lag=LAG, p_low=P_LOW):
        super().__init__(name)
        self.LAG = float(lag)
        self.P_LOW = float(p_low)
        self._base_p = float(getattr(self, "p_conv", 0.71) or 0.71)
        self._last_scores = None
        self._seat = None
        self.room_scores = [0.0, 0.0, 0.0, 0.0]
        self.n_dec = 0
        self.n_absorbed = 0
        self.n_lag = 0

    def _absorb_scores(self, sc):
        """把**新出现**的结算向量累加进房内局势；返回是否吸收了新结算。

        幂等：同一个向量重复出现只算一次（`view["scores"]` 在下一个结算到来前会保持不变）。
        """
        if not isinstance(sc, (list, tuple)) or len(sc) != 4:
            return False
        try:
            v = [float(x) for x in sc]
        except (TypeError, ValueError):
            return False
        if self._last_scores is not None and v == self._last_scores:
            return False
        self._last_scores = v
        if all(abs(x) < 1e-9 for x in v):
            return False
        for i in range(4):
            self.room_scores[i] += v[i]
        if max(abs(x) for x in self.room_scores) > GUARD:
            self.room_scores = [0.0, 0.0, 0.0, 0.0]
        self.n_absorbed += 1
        return True

    def lagging(self):
        try:
            me = int(self._seat)
        except (TypeError, ValueError):
            return False
        if not (0 <= me < 4):
            return False
        try:
            return (max(self.room_scores) - self.room_scores[me]) >= self.LAG
        except Exception:
            return False

    def decide(self, view):
        self.n_dec += 1
        view = view or {}
        try:
            self._seat = view.get("seat")
        except Exception:
            self._seat = None
        self._absorb_scores(view.get("scores"))
        lag = self.lagging()
        if lag:
            self.n_lag += 1
        self.p_conv = self.P_LOW if lag else self._base_p
        return super().decide(view)
