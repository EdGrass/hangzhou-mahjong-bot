# -*- coding: utf-8 -*-
"""SpeedC135 —— `speedtugc` 的**单变量**候选：未听牌段的并列改按 **真·进张(ukeire)** 打破。

与基线唯一的差别：基线 `_best_discard_t` 的排序键是
    (向听, −听牌张数[仅 s==0], _pref, 保留摸切)
而 `s>0` 时它**完全不看进张**（`wcnt` 只在 s==0 时算），并列全部落到静态 `_pref`。
本候选把 `_pref` 的位置换成 **真进张**：
    (向听, −听牌张数[s==0], **−real_ukeire[s>0]**, _pref, 保留摸切)

与**已作废**的 `speedc132`/`speedc117` 的区别：那两个用的是
`c069routes.ukeire_counts` —— **"邻接张数"代理（不看向听）**，真机证明会把牌打坏
（听牌率 13.3% vs 基线 27.2%）。本候选用的是 `bot/ukeire.py:real_ukeire`：
    t 是进张 ⇔ ∃d：shanten(H−d+t) < shanten(H)；live 扣「自家手牌 + 弃牌河 + 四家副露」。

成本：只对**最小向听组**（通常 2–4 张）各算一次真进张 ⇒ ≈1 ms/张 ⇒ 每个决策 ~3 ms（实测单次 0.92ms）。
纪律：**这条链必须在轨迹级核对**（A/B 的 `tools/ab_mechanism.py` 会给出听牌率/平均向听）；
若听牌率没有改善就停臂——这是上两次的教训。
"""
from __future__ import annotations

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts


def _best_discard_realukeire(hand, drawn, exposed, gangs, god_meld=True, view=None):
    cands = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs, god_meld=god_meld)
        except ValueError:
            continue
        cands.append((d, rem, s))
    if not cands:
        return hand[0]
    smin = min(c[2] for c in cands)
    vis = None
    if view:
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            vis = None
    best_key, best_tile = None, None
    for d, rem, s in cands:
        if s != smin:
            continue
        wcnt = 0
        u = 0.0
        if s == 0:
            try:
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                wcnt = 0
        else:
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld)
                u = float(uu[0] or 0)
            except Exception:
                u = 0.0
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedC135(SpeedTUGC):
    def __init__(self, name="speedc135"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _best_discard_realukeire(hand, drawn, exposed, gangs,
                                        god_meld=self.GOD_MELD, view=view)
