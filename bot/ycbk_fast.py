# -*- coding: utf-8 -*-
"""FastYCBK —— 给快版策略加 YouCaiBiKao=true 的合法胡闸门（不引入 c135 重型出牌层）。

c148/c153 的规则正确，但继承 c146，缺少 c164/c165/c166 的轻量路线/副露增益。
本 mixin 只复制合法性判断和决定路径，供 fast 候选多继承使用。
"""
from __future__ import annotations

from mahjong.fan import calc as calc_fan
from mahjong.hu import is_baotou

GOD_TILE = "白"


class FastYCBKMixin:
    GOD_MELD = False
    YOU_CAI_BI_KAO = True
    FORCE_BAOTOU_ON_BLOCK = False

    def _ycbk_violation(self, view, pre_hand, exposed, gangs):
        hand = list(view.get("my_hand") or [])
        if GOD_TILE not in hand:
            return False
        god = view.get("god") or {}
        if int(god.get("chain_count") or 0) > 0:
            return False
        try:
            if is_baotou(list(pre_hand), allow_qidui=(exposed == 0 and gangs == 0),
                         exposed_melds=exposed, gangs=gangs):
                return False
        except Exception:
            pass
        drawn = view.get("drawn_tile")
        if drawn:
            try:
                info = calc_fan(list(pre_hand), drawn,
                                {"count": int(god.get("chain_count") or 0),
                                 "piao": int(god.get("piao_count") or 0)},
                                base=1, exposed_melds=exposed, gangs=gangs)
                det = info.get("detail") or []
                if any(str(x).startswith("七对") or str(x).startswith("豪华七对") for x in det):
                    return False
            except Exception:
                pass
        return True

    def _blocked_hu_action(self, view):
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds
                    if isinstance(m, dict) and m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        pre = list(hand)
        if drawn and drawn in pre:
            pre.remove(drawn)
        if not self._ycbk_violation(view, pre, exposed, gangs):
            return None
        if self.FORCE_BAOTOU_ON_BLOCK:
            try:
                god = view.get("god") or {}
                chain = {"count": int(god.get("chain_count") or 0),
                         "piao": int(god.get("piao_count") or 0)}
                tile = self._best_giveup(list(hand), exposed, gangs, 0, chain)
                if tile is not None:
                    return {"action": "discard", "tile": tile}
            except Exception:
                pass
        try:
            tile = self._pick_discard(hand, drawn, exposed, gangs, view=view)
        except Exception:
            tile = hand[0] if hand else ""
        return {"action": "discard", "tile": tile}

    def decide(self, view):
        act = super().decide(view)
        if isinstance(act, dict) and act.get("action") == "hu" and self.YOU_CAI_BI_KAO:
            blocked = self._blocked_hu_action(view)
            if blocked is not None:
                return blocked
        return act


class FastYCBKForceMixin(FastYCBKMixin):
    FORCE_BAOTOU_ON_BLOCK = True
