# -*- coding: utf-8 -*-
"""`speedgangfix` —— R939 的 P0 修补臂：**带杠手牌的弃牌器不再退化成 `return hand[0]`**。

问题（R937/R938/R939 三连）：
  带杠手牌暗牌 = `14-3e-g ≡ 13-3e`（杠按 3 张计），而 `exact_shanten`/`real_ukeire` 的规格是 `13-3e-g`
  ⇒ **对带杠手牌的每个候选都抛 ValueError** ⇒ `speedc151._pick_discard_route` 的 `cands` 为空
  ⇒ **`return hand[0]`（任意一张牌）**。
  实测后果：含杠局**保向听率 ME 83.1% vs TOP32 100.0%**（普通局 98.9% vs 99.5%）⇒ 每 6 次弃牌有 1 次听坏。

本臂的唯一差别：
  `gangs > 0` 时改用**杠按 3 张计**的约定（`exposed_melds=exposed, gangs=0`）算向听/进张/等张；
  其余键（路线加成、静态偏好 `_pref`、摸切）与 c151 **完全一致**。
  `gangs == 0` 时**逐位委托 `super()._pick_discard`** ⇒ **构造上保证与 c151 完全相同**（非杠零回归）。

⚠ 边界：本臂只修**弃牌器**。带杠手牌的**吃碰**仍被 `speedtugc.decide` 的 chi 分支与
  `speedc136._want_claim` 的长度检查挡住（那两处需改 `decide`/`_want_claim`，见 runbook §10.18）。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedc151 import SpeedC151, _pair_count
from .speedc135 import _pref
from .speedt import _best_discard_t
from .ukeire import real_ukeire, visible_counts


def _pick_discard_route_gangaware(hand, drawn, exposed, gangs, god_meld=True,
                                  view=None, deadline=None, fallback=None,
                                  route_bonus=8.0, gate_river=0):
    """`speedc151._pick_discard_route` 的**杠感知**版本（唯一差别：规格用 `13-3e`）。"""
    if deadline is not None and fallback is None:
        fallback = _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
    cands = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0), exposed_melds=exposed,
                              gangs=0, god_meld=god_meld)
        except ValueError:
            continue
        cands.append((d, rem, s))
    if not cands:
        # 修正后不应到这里；兜底用基线的有界弃牌（绝不再 `return hand[0]`）
        return _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
    if deadline is not None and time.monotonic() >= deadline:
        return fallback
    smin = min(c[2] for c in cands)
    _river_len = 0
    try:
        _river_len = int(len((view or {}).get("river") or []))
    except Exception:
        _river_len = 0
    _bonus_on = (gate_river <= 0) or (_river_len >= gate_river)
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
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=0))
            except Exception:
                wcnt = 0
        else:
            if deadline is not None and time.monotonic() >= deadline:
                return fallback
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=0, visible=vis,
                                 god_meld=god_meld, deadline=deadline)
                if uu[0] is None or uu[1] is None:
                    return fallback
                u = float(uu[0] or 0)
            except Exception:
                if deadline is not None:
                    return fallback
                u = 0.0
            if _bonus_on:
                pc = _pair_count(rem)
                if pc <= 2:
                    u += route_bonus
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedGangFix(SpeedC151):
    """P0 修补臂（只修弃牌器）。"""

    def __init__(self, name="speedgangfix", budget_ms=None):
        super().__init__(name, budget_ms=budget_ms)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        if not gangs:
            return super()._pick_discard(hand, drawn, exposed, gangs, view=view)
        deadline = None
        fallback = None
        if self.budget_ms is not None:
            fallback = _best_discard_t(hand, drawn, exposed, gangs,
                                       god_meld=self.GOD_MELD)
            deadline = time.monotonic() + self.budget_ms / 1000.0
        return _pick_discard_route_gangaware(hand, drawn, exposed, gangs,
                                             god_meld=self.GOD_MELD, view=view,
                                             deadline=deadline, fallback=fallback)
# ---------------------------------------------------------------- 第二半：带杠手牌的吃碰
from .speedc136 import _after_best, _state
from .speed import _chi_pairs


def _melds_info(view):
    melds = view.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
    return e, g


class SpeedGangFixClaim(SpeedGangFix):
    """R941：在 SpeedGangFix 之上，**恢复带杠手牌的吃/碰**。

    `_want_claim`：`gangs == 0` ⇒ `super()`（逐位不变）；`gangs > 0` ⇒ 用**杠感知规格 `13-3e`** 重跑
    c136 的两条判据 —— ①向听严格下降即接受 ②等向听但真进张变好即接受。
    `decide`：只在「带杠 + 响应窗口」时接管 chi 分支（父类那条 `len(hand)==13-3e-g` 会把 chi 永久堵死），
    其余一律 `super().decide(view)` ⇒ 非杠与 draw 路径零改动。
    """

    def _want_claim(self, view, kind, pair=None):
        e, g = _melds_info(view)
        if not g:
            return super()._want_claim(view, kind, pair)
        if kind not in ("chi", "peng"):
            return False
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        if not offer or len(hand) != 13 - 3 * e:
            return False
        try:
            vis = visible_counts(hand, river=view.get("river"),
                                 all_melds=view.get("all_melds"))
        except Exception:
            vis = None
        before = _state(hand, e, 0, vis, self.GOD_MELD)
        if before is None or before[1] is None:
            return False
        if kind == "chi":
            opts = [("chi", p) for p in _chi_pairs(hand, offer)]
            if pair is not None:
                opts = [("chi", pair)]
        else:
            opts = [("peng", None)]
        for k, p in opts:
            after = _after_best(hand, offer, k, p, e, 0, vis, self.GOD_MELD)
            if after is None or after[1] is None:
                continue
            if after[0] < before[0]:
                return True                      # ① 向听严格下降
            if after[0] == before[0] and (after[1] or 0.0) > (before[1] or 0.0):
                return True                      # ② 等向听但真进张变好
        return False

    def decide(self, view):
        try:
            phase = str(view.get("phase") or "")
            e, g = _melds_info(view)
        except Exception:
            return super().decide(view)
        if not g or not phase.startswith("response_"):
            return super().decide(view)
        hand = list(view.get("my_hand") or [])
        offer = view.get("offer_tile")
        if len(hand) != 13 - 3 * e or not offer:
            return {"action": "pass", "tile": ""}
        if phase == "response_peng":
            cnt = hand.count(offer)
            if cnt >= 3 and self._want_claim(view, "gang_ming"):
                return {"action": "gang", "tile": offer}
            if cnt >= 2 and self._want_claim(view, "peng"):
                return {"action": "peng", "tile": offer}
            return {"action": "pass", "tile": ""}
        if phase == "response_chi":
            chi_cnt = sum(1 for m in (view.get("melds") or [])
                          if isinstance(m, dict) and m.get("type") == "chi")
            if chi_cnt < 2:
                for pair in _chi_pairs(hand, offer):
                    if self._want_claim(view, "chi", pair):
                        return {"action": "chi", "tile": offer}
            return {"action": "pass", "tile": ""}
        return super().decide(view)

class SpeedGangFixLate(SpeedGangFixClaim):
    """R952：**组合臂** = `SpeedGangFix`（杠感知）＋ `SpeedRouteLate`（多对子惩罚**晚期门控**）。

    依据：R951 证"对数有害"只在晚期成立（早期为正/持平）⇒ 无条件惩罚（c151 的 8.0）前提不成立；
    R94x 又证带杠手牌在现行代码下弃 `hand[0]` ⇒ 任何要上线的臂都必须带杠感知修补。
    本臂对**所有手牌**调用同一个参数化函数：
      · 非杠手牌 ⇒ 与 `_pick_discard_route_bonus(..., gate_river=16)` 等价（可验证逐位一致）；
      · 带杠手牌 ⇒ 用修正约定 `13-3e`（不抛错、不弃 `hand[0]`）。
    """

    ROUTE_BONUS = 8.0
    GATE_RIVER = 16

    def __init__(self, name="speedgangfixlate"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        deadline = None
        fallback = None
        if self.budget_ms is not None:
            fallback = _best_discard_t(hand, drawn, exposed, gangs,
                                       god_meld=self.GOD_MELD)
            deadline = time.monotonic() + self.budget_ms / 1000.0
        return _pick_discard_route_gangaware(
            hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
            deadline=deadline, fallback=fallback,
            route_bonus=self.ROUTE_BONUS, gate_river=self.GATE_RIVER)
