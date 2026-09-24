# -*- coding: utf-8 -*-
"""SpeedC141 —— `speedtugc` 的**单变量**候选：把「财飘」计进弃胡判据。

问题（2026-09-16 真实复盘实测，R116/R117/E080/E081）：
`bot/speedtug.py::_best_giveup` 估「弃胡后爆头形那一摸的番」时，
传的是**弃牌前的 chain**。但本作规则里**弃白板（财飘）本身是一个链动作**
（`chain_count+1`、`piao_count+1`，倍率 ×2；见 `mahjong/sim.py` 动作链说明与
`mahjong/fan.py::PIAO_NAMES`）。因此当**弃掉的那张是白板**时，
现有判据把爆头番**低估了 2 倍**。

真实后果：手牌是「4 面子 + 2 白」（= 已爆头：任意摸都胡，fan_now=2），
弃一张白 → 仍是 4 面子 + 白孤 = **爆头不变**，但多一层财飘 ⇒ 番 4。
- 现有判据：0.71 × 2 = 1.42 ≤ 2 ⇒ **不弃胡**（直接胡掉）；
- 修正判据：0.71 × 4 = 2.84 > 2 ⇒ **弃胡换财飘爆头**。

真机语料实测（`var/replays/*` 全信息复盘，我方 23,541 局）：
- 「可弃胡窗口」2,295 个，现有判据触发 1,063 个，修正判据触发 1,120 个；
- **新增 57 个窗口全部来自弃白（财飘）**：fan_now=2 → 45 个、=4 → 11 个、=8 → 1 个；
- 折算 ≈ **0.19 次/房**，按「爆头 ≈ +11 分/次」且财飘档本身 ×2（≈+20~48 分/次），
  预估 **+4~5 原始分/房**（低于单次 A/B 可判定线，属于「组合臂」成分）。
- 反面证据：全场 103 次财飘胡（其中 100 次同时爆头），**我方 0 次**。

与基线的差异**只有这一处**（`_best_giveup` 的 chain 记账），其余 100% 继承 `SpeedTUGC`。
"""
from __future__ import annotations

from mahjong.hu import is_baotou
from mahjong.tiles import GOD_TILE

from .speedtugc import SpeedTUGC


class SpeedC141(SpeedTUGC):
    def __init__(self, name="speedc141"):
        super().__init__(name)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        """返回 (弃牌)；判据同 SpeedTUG，但**弃白=财飘时先把 chain/piao +1 再估番**。"""
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
        return best if self.p_conv * best_fan > fan_now else None
