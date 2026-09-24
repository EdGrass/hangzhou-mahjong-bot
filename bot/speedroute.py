# -*- coding: utf-8 -*-
"""`speedroute` —— c151 的**单旋钮阶梯**：多对子惩罚的强度 `ROUTE_BONUS`。

为什么做这个阶梯（R883）：
- `bot/speedc151.py` 的弃牌键 = `(向听, −听牌张数[s==0], −(real_ukeire + 路线加成)[s>0], _pref, 摸切)`，
  其中 `路线加成 = ROUTE_BONUS × 1{弃牌后对数 ≤ 2}`；
- 但**该参数是"先取一个较大的值"的猜测**（原文：`ROUTE_BONUS = 8.0` … "若读数显示过度拆对再降"），
  **从未被标定**；
- 实测（R883，9 房 3,434 个摸牌决策）：c151 的 `_pick_discard` **从不抛异常**（静默回退路径从未触发），
  但它相对"纯最大活张"有 **3.5% 的次优**，且次优幅度**恰好都 ≤8 live** ——
  即**这 3.5% 就是 8.0 的加成在覆盖活张差**，不是 bug、也不是未解释的残差；
- ⇒ 既然"对数 ≤2"的方向有强证据（≥3 对时第 8 巡听牌率 13~30%，1~2 对时 39~72%），
  而**强度 8.0 是猜的**，那就把它做成一阶梯，在**同一次战役里**同时测两端。

本模块提供两个臂（与 c151 **只差这一个常数**）：
- `SpeedRoute2`  （bonus=2.0）：弱化多对子惩罚 ⇒ 更接近纯活张；
- `SpeedRoute16` （bonus=16.0）：强化 ⇒ 更积极地压对数。

⚠ 实现说明：`_route_bonus` 用的是 `speedc151` 模块级常量，而 M=10 下**不能**改全局（并发不安全），
故这里**复制**了 `_pick_discard_route` 的实现并把 bonus 变成函数参数（与 `speedc152` 自带一份
`_pick_discard_graded` 的做法一致）。代价：c151 该函数将来若修，本模块不会自动继承。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc135 import _pref
from .speedc150 import SpeedC150
from .speedc151 import _pair_count
from .speedt import _best_discard_t
from .ukeire import real_ukeire, visible_counts


def _pick_discard_route_bonus(hand, drawn, exposed, gangs, god_meld=True, view=None,
                              deadline=None, fallback=None, route_bonus=8.0,
                              gate_river=0):
    """与 `speedc151._pick_discard_route` 逐位等价，**除了** `route_bonus` 可指定。"""
    if deadline is not None and fallback is None:
        fallback = _best_discard_t(hand, drawn, exposed, gangs, god_meld=god_meld)
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
    if deadline is not None and time.monotonic() >= deadline:
        return fallback
    smin = min(c[2] for c in cands)
    # R886：可选的**时间门** —— 多对子惩罚只在河长 >= gate_river 后生效
    #   依据：对度差异的成因窗口（巡 3~5）里，**我们已经比顶级少对子**
    #   （>=3 对：26.0~26.6% vs 28.7~29.8%）⇒ 一律惩罚可能**起步就压错方向**，而后期尚可能真的该压。
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
                wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
            except Exception:
                wcnt = 0
        else:
            if deadline is not None and time.monotonic() >= deadline:
                return fallback
            try:
                uu = real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis,
                                 god_meld=god_meld, deadline=deadline)
                if uu[0] is None or uu[1] is None:
                    return fallback
                u = float(uu[0] or 0)
            except Exception:
                if deadline is not None:
                    return fallback
                u = 0.0
            try:
                if _bonus_on and _pair_count(rem) <= 2:
                    u += route_bonus
            except Exception:
                pass
        key = (s, -wcnt, -u, _pref(d, hand), -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class _RouteBase(SpeedC150):
    ROUTE_BONUS = 8.0
    GATE_RIVER = 0        # 0 = 不门控（与 c151 逐位等价）；>0 = 河长达标后才计算多对子惩罚

    def __init__(self, name="speedroute"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_route_bonus(hand, drawn, exposed, gangs,
                                         god_meld=self.GOD_MELD, view=view,
                                         route_bonus=self.ROUTE_BONUS,
                                         gate_river=self.GATE_RIVER)


class SpeedRoute2(_RouteBase):
    ROUTE_BONUS = 2.0

    def __init__(self, name="speedroute2"):
        super().__init__(name)


class SpeedRoute16(_RouteBase):
    ROUTE_BONUS = 16.0

    def __init__(self, name="speedroute16"):
        super().__init__(name)


class SpeedRouteLate(_RouteBase):
    """★ R886：多对子惩罚**推迟到河长 >=16（约巡 4）才生效**。

    依据：成因窗口（巡 3~5）对比，顶级**持更多对子**（>=3 对 28.7~29.8% vs 我们 26.0~26.6%）
    但到了第 8 巡，多对子与听牌率强负相关。⇒ 合理猜测：**早期不该压，晚期才该压**；
    现役 c151 是**从第一张就开始压**。本臂只改"**何时开始压**"（GATE_RIVER=16），强度仍为 8.0。
    """

    GATE_RIVER = 16

    def __init__(self, name="speedroutelate"):
        super().__init__(name)


class SpeedRoute0(_RouteBase):
    """★ R901：**去掉多对子惩罚**（bonus = 0.0）—— 阶梯的另一端。

    依据（R886）：在成因窗口（巡 3~5）我们**已经比顶级更少对子**
    （>=3 对：26.0~26.6% vs 28.7~29.8%）；而 c151 的 `ROUTE_BONUS=8.0` 是**继续压低对子**。
    若那个惩罚方向过头，本臂（bonus=0）应该更好。
    与 c151 的**唯一差别就是这个常数**（其余机制：副露门控/明杠/自杠/放弃胡/真进张全部沿用）。

    那么阶梯就完整了：`{0, 2, 8(现役), 16}`（强度）+ `SpeedRouteLate`（时机）
    ⇒ 下一役可直接选最有信息量的两端（如 `{Route0, Route16}`）做“这个旋钮到底有没有用、往哪边”的判定。
    """

    ROUTE_BONUS = 0.0

    def __init__(self, name="speedroute0"):
        super().__init__(name)

