# -*- coding: utf-8 -*-
"""SpeedC198 = `speedc135`（真进张排序）+ **爆头形保形**（只在"可胡"点上生效）。

依据（R526/R527）：
  - 爆头 = **听牌态摸任意一张都能胡**（`mahjong.hu.is_baotou`），白（财神）越多越易达成（实测 白×1 20% / ×2 41.5% / ×3 68.2%）。
  - 真机 A/B：c135 用"更快"换掉了 **有爆头形% −4.6pp（~2σ）**、平均对数 −0.15，且爆头占胡 −3.5pp
    ⇒ 与项目踩过的坑同形（`候选库`："不要为了抬听牌率去换番数"）。
  - 本候选**只加一条**：当**当前可胡**且最小向听候选里**存在能形成爆头形的弃牌**时，
    在这些候选里按 c135 的键选；否则完全退回 c135。
  - 因为只在"可胡"点算 `is_baotou`（约占决策 1.3%），延迟代价可忽略。
"""
from __future__ import annotations

from .speedc135 import _best_discard_realukeire
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts
from mahjong.hu import is_baotou, is_win
from mahjong.shanten_exact import shanten as exact_shanten


class SpeedC198(SpeedTUGC):
    def __init__(self, name="speedc198"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        # 只在"当前可胡"时做爆头形保形；其余情况 1:1 等于 c135
        try:
            can_win = bool(is_win(list(hand), exposed_melds=exposed, gangs=gangs))
        except Exception:
            can_win = False
        if not can_win:
            return _best_discard_realukeire(hand, drawn, exposed, gangs,
                                            god_meld=self.GOD_MELD, view=view)
        vis = None
        if view:
            try:
                vis = visible_counts(hand, river=view.get("river"),
                                     all_melds=view.get("all_melds"))
            except Exception:
                vis = None
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs)
            except Exception:
                continue
            cands.append((d, rem, s))
        if not cands:
            return hand[0]
        smin = min(c[2] for c in cands)
        keep = []
        for d, rem, s in cands:
            if s != smin:
                continue
            try:
                if is_baotou(rem, allow_qidui=(exposed == 0 and gangs == 0),
                             exposed_melds=exposed, gangs=gangs):
                    keep.append((d, rem, s))
            except Exception:
                continue
        if not keep:
            return _best_discard_realukeire(hand, drawn, exposed, gangs,
                                            god_meld=self.GOD_MELD, view=view)
        best_key, best_tile = None, None
        for d, rem, s in keep:
            wcnt = 0
            u1 = 0.0
            if s == 0:
                from mahjong.shanten import waits
                try:
                    wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
                except Exception:
                    wcnt = 0
            else:
                try:
                    u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
                except Exception:
                    u1 = 0.0
            key = (s, -wcnt, -u1, _pref(d, hand), -1 if d == drawn else 0)
            if best_key is None or key < best_key:
                best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
