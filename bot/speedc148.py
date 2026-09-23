# -*- coding: utf-8 -*-
"""SpeedC148 —— **有财必拷响（YouCaiBiKao=true）保险臂**。

为什么要有它（2026-09-16 实测）：
门户 `GET /portal/api/tournaments` 目前**只有二测那一场**（如 t_xxxxxxxxxxxx，YouCaiBiKao=false），
**一个月后的正式赛尚未发布**；而接入指南 §1.6 明确：`M / Rounds / BaseScore / YouCaiBiKao /
各窗口秒数` **每场锦标赛可不同**，必须以 `GET /api/tournaments/me/rules`（或 /{id}）的 config 为准。
`YouCaiBiKao`（有财必拷响）= **手上有财神时不允许平胡，必须爆头/杠开才能胡** ——
一旦正式赛开了这个开关，而我们的策略照旧声明"平胡"：
① 会被服务端拒（执行层 409 / 机会丢失），② 整局的**打点路线**也该改（白要留作万能听 → 爆头）。
**本臂就是那条保险**：在 C146（明杠+自杠+吃碰+财飘）之上
  1) `GOD_MELD=False` —— 弃牌评估里白**不补面子**，倾向保留白孤 ⇒ 朝「4 面子+白孤=爆头」走
     （与 C141 的财飘、C134/C144 的杠链天然叠加：杠/财飘 + 爆头 = fan 4/8）；
  2) `YOU_CAI_BI_KAO=True` —— **胡牌合法性闸门**：手上有白、且既非爆头、也无链（chain_count=0）
     时**拒绝声明 hu**，改为按同一弃牌钩子出牌（保住这一局的摸牌/换听机会，而不是白交一个被拒的 hu）。

⚠ **默认不启用**：只有确认正式赛 config 里 `YouCaiBiKao=true` 时才切到本策略（见 STATUS §4c-11 的操作步骤）。
⚠ 已知简化：C136 的副露门控在 `GOD_MELD=False` 下的评估已随本臂打通（`_state/_after_best` 传入 `self.GOD_MELD`）。
"""
from __future__ import annotations

from mahjong.fan import calc as calc_fan
from mahjong.hu import is_baotou

from .speedc146 import SpeedC146

GOD_TILE = "白"


class SpeedC148(SpeedC146):
    GOD_MELD = False          # 白只作万能听（爆头路线）
    YOU_CAI_BI_KAO = True     # 有财必拷响：手上有财 ⇒ 只能爆头/杠开胡

    def __init__(self, name="speedc148"):
        super().__init__(name)

    def _ycbk_violation(self, view, pre_hand, exposed, gangs):
        """手上有财神、且这一胡是**平胡**（既非爆头、也无链、也非七对） ⇒ 本规则下不合法。

        依据指南 §1.6 的口径：「有财必拷响 = 手上有财神时**不允许平胡**，必须爆头/杠开才能胡」。
        因此：七对/豪华七对（不是平胡）允许；爆头允许；链（杠开/财飘，`chain_count>0`）允许。
        """
        hand = list(view.get("my_hand") or [])
        if GOD_TILE not in hand:
            return False
        god = view.get("god") or {}
        if int(god.get("chain_count") or 0) > 0:
            return False                                  # 杠开 / 财飘链：允许
        try:
            if is_baotou(list(pre_hand), allow_qidui=(exposed == 0 and gangs == 0),
                         exposed_melds=exposed, gangs=gangs):
                return False                              # 爆头：允许
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
                    return False                          # 七对家族：不是平胡，允许
            except Exception:
                pass
        return True

    def decide(self, view):
        act = super().decide(view)
        if not (isinstance(act, dict) and act.get("action") == "hu" and self.YOU_CAI_BI_KAO):
            return act
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
            return act
        try:
            tile = self._pick_discard(hand, drawn, exposed, gangs, view=view)
        except Exception:
            tile = hand[0] if hand else ""
        return {"action": "discard", "tile": tile}
