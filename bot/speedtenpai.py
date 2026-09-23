# -*- coding: utf-8 -*-
"""`speedtenpai` —— c151 的**可证占优**小修：**听牌时按"活等张数"而不是"等张种类"破并列**。

背景（R827/R828 已量）：
- 现役键在 `s == 0`（听牌）用的是 `−len(waits(hand))`，即**等张的"种类数"**，
  完全**不看每种等张还剩几张**（四张里已经河/副露掉三张的"死等"与全新的"活等"同分）；
- 实测：若改成"活等张数"（`Σ live(t)`，扣自家手牌 + 弃牌河 + 四家副露），
  **约 0.94% 的听牌决策会改变**（R827/R828）⇒ 不单独占一役，属**搭车项**（本臂就是它的载体）。

本臂（相对 c151 的唯一差别）：
    先取 c151 的选择 `base`；**若 `base` 处于听牌（s==0）**，则在**全部 `s==0` 的弃牌**中
    找"活等张数严格更多"的那一张；有则改选它，否则原样返回 `base`。
  - ⇒ **可证占优（仅限「胡牌概率」）**：向听不变，**活等张数只增不减**；
  ⚠⚠ **但得分是 番 × 胡**：实测（固定语料 700 局面）在 15 个被改变的听牌决策里，
  **2/15 例最高番会降低（最差 −2 番）** ⇒ **无番保护的那档不是整体占优，而是「频率换番」的交易**；
  因此本模块提供**两档**：
  - ⇒ **下行有界**：不在 s==0 的局面**逐位不变**（不动非听牌决策）；
  - ⇒ 代价极低：只在 `s==0` 时多算 ≤14 次 `waits + 活张统计`。

方向护栏（可测）：① 非听牌局面逐位等于 c151；② 新臂的 (向听, 活等张) 弱优于 c151；③ 非 no-op。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from mahjong.fan import calc as calc_fan

from .speedc151 import SpeedC151
from .ukeire import visible_counts


class _TenpaiBase(SpeedC151):
    """听牌阶段改按活等张排序。FAN_GUARD=True 时额外要求不降番。"""
    FAN_GUARD = False

    def __init__(self, name="speedtenpai"):
        super().__init__(name)

    def _max_fan(self, rem13, exposed, gangs, view):
        """该听牌形在最好等张上的最高番（取不到则 None）。"""
        try:
            ws = waits(rem13, exposed_melds=exposed, gangs=gangs)
        except Exception:
            return None
        god = (view or {}).get("god") or {}
        chain = {"count": int(god.get("chain_count") or 0),
                 "piao": int(god.get("piao_count") or 0)}
        best = None
        for wt in (ws or []):
            try:
                r = calc_fan(list(rem13), wt, chain, base=1,
                             exposed_melds=exposed, gangs=gangs)
            except Exception:
                continue
            if r.get("hu"):
                f = r.get("fan") or 0
                if best is None or f > best:
                    best = f
        return best

    def _live_wait_count(self, hand13, exposed, gangs, vis):
        """\u5f53\u524d\u542c\u724c\u5f62\u7684**\u6d3b\u7b49\u5f20\u6570**\uff08\u603b\u5f20\u6570\uff0c\u6263\u53ef\u89c1\uff09\u3002"""
        try:
            ws = waits(hand13, exposed_melds=exposed, gangs=gangs)
        except Exception:
            return None
        if not ws:
            return 0
        tot = 0
        for t in ws:
            tot += max(0, 4 - int(vis.get(t, 0)))
        return tot

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        base = super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        if base not in hand:
            return base
        vis = None
        if view:
            try:
                vis = visible_counts(hand, river=view.get("river"),
                                     all_melds=view.get("all_melds"))
            except Exception:
                vis = None
        if vis is None:
            return base
        # base \u7684\u5411\u542c\uff08\u5f03\u724c\u540e\uff09
        try:
            rem0 = list(hand)
            rem0.remove(base)
            s0 = exact_shanten(rem0, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs, god_meld=self.GOD_MELD)
        except Exception:
            return base
        if s0 != 0:
            return base                          # \u975e\u542c\u724c\uff1a\u9010\u4f4d\u4e0d\u53d8
        live0 = self._live_wait_count(rem0, exposed, gangs, vis)
        if live0 is None:
            return base
        best_t, best_live = None, live0
        for d in sorted(set(hand)):
            if d == base:
                continue
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs, god_meld=self.GOD_MELD)
            except Exception:
                continue
            if s != 0:
                continue
            lv = self._live_wait_count(rem, exposed, gangs, vis)
            if lv is None:
                continue
            if lv <= best_live:
                continue
            if self.FAN_GUARD:
                f_new = self._max_fan(rem, exposed, gangs, view)
                f_old = self._max_fan(rem0, exposed, gangs, view)
                if f_new is not None and f_old is not None and f_new < f_old:
                    continue          # 不降番才改（占优档）
            best_t, best_live = d, lv
        return best_t if best_t is not None else base


class SpeedTenpaiLive(_TenpaiBase):
    """频率档：只看活等张（可能降番）。"""
    FAN_GUARD = False

    def __init__(self, name="speedtenpailive"):
        super().__init__(name)


class SpeedTenpaiLiveFan(_TenpaiBase):
    """占优档：活等张更多且不降番。"""
    FAN_GUARD = True

    def __init__(self, name="speedtenpailivefan"):
        super().__init__(name)
