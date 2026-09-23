# -*- coding: utf-8 -*-
"""SpeedC215 —— c211 的**单变量**候选：把并列 tiebreak 从静态 `_pref` 换成
项目里已有的**教师候选排序器** `bot/c089rank.Ranker`（81 维，学"顶级玩家会弃哪张"，
权重 `var/c089_ranker_net.pt` 现成）。

动机（R586~R588）：缺口已定位到"起手 2~3 向听的中等手牌能否越过听牌线"（−3.2pp），
而所有**手写规则型**中间量在两边都相同 ⇒ 换用"学出来的偏好"是唯一还没试过的评估器。
与 C039"照搬顶级偏好更负"的区别：那一次是**直接照搬整张弃牌**；
本候选只把它用在**并列 keys 的最后一层**（主键仍是 向听 → 活张数/进张 → …），下行有界。

⚠ 先测分歧率（R545 纪律：<10% 视为"没跑到"）。
"""
from __future__ import annotations

import os

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc211 import SpeedC211
from .speedc152 import W_GRADED, _pair_count
from .ukeire import real_ukeire, visible_counts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RANKER = os.path.join(ROOT, "var", "c089_ranker_net.pt")


class SpeedC215(SpeedC211):
    def __init__(self, name="speedc215", ranker_path=None):
        super().__init__(name)
        try:
            from .c089rank import Ranker
            self.ranker = Ranker(ranker_path or DEFAULT_RANKER)
        except Exception:
            self.ranker = None

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs, god_meld=self.GOD_MELD)
            except ValueError:
                continue
            cands.append((d, rem, s))
        if not cands:
            return hand[0]
        smin = min(c[2] for c in cands)
        vis = None
        if view:
            try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            except Exception: vis = None
        # 主键（不含偏好项）
        main = {}
        for d, rem, s in cands:
            if s != smin: continue
            wcnt = 0.0; u = 0.0
            if s == 0:
                try:
                    ws = waits(rem, exposed_melds=exposed, gangs=gangs); v = vis or {}
                    wcnt = float(sum(max(0, 4 - int(v.get(t, 0))) for t in ws))
                except Exception: wcnt = 0.0
            else:
                try:
                    uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis, god_meld=self.GOD_MELD)
                    u = float(uu[0] or 0)
                except Exception: u = 0.0
                u += float(W_GRADED.get(_pair_count(rem), 0.0))
            main[d] = (s, -wcnt, -u)
        if not main:
            return hand[0]
        best_main = min(main.values())
        tied = [d for d, k in main.items() if k == best_main]
        if len(tied) == 1 or self.ranker is None:
            return tied[0] if tied else hand[0]
        rl = float(len((view or {}).get("river") or []))
        try:
            ordered = self.ranker.order(hand, sorted(tied), exposed, gangs, rl)
        except Exception:
            ordered = []
        if ordered:
            # 教师最可能选的那张里，优先非摸切（与 c211 末位同向）
            top = [d for d in ordered if d != drawn] or ordered
            return top[0]
        return tied[0]
