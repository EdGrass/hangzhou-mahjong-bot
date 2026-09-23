# -*- coding: utf-8 -*-
"""SpeedC200 —— c135 的**单变量**候选：并列键里加入"**两摸内的和了期望**"（而不是进张数）。

依据 R543：c135 把"到听牌"提快 4.7pp，却把"听牌后胡率"拉低 2.1pp（活等张 −0.71），
净和了率只 +0.84pp（配对 rollout）。⇒ 目标函数里必须含**到达时的待ち宽度**。

本候选：在 c135 的 (向听, 听牌张数, **真进张**) 之后、`_pref` 之前，插入
    win2(d) = Σ_{t ∈ rem 的进张（按活张取前 K）} live(t) × WW(rem + t)
其中 WW(h14) = "h14 摸完后，能否弃成听牌以及该听牌的活等张数" —— 即"再摸一张能不能和、和多少张"。
⇒ 它把"速度"和"到达时的待ち宽度"放进同一个数里（近似的**两摸内和了期望**）。

延迟：只在最小向听组、只取前 K=4 个进张 ⇒ 每决策 ~4×(|hand| 次向听) 次调用，带 deadline 保护。
"""
from __future__ import annotations
import time
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from .speedc135 import _best_discard_realukeire
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import visible_counts

TILES = [t + s for s in ("w", "b", "t") for t in "123456789"] + ["东", "南", "西", "北", "中", "发", "白"]


def _adv(rem, e, g, s_now):
    out = []
    for t in TILES:
        ok = False
        for d in set(rem):
            hh = list(rem); hh.remove(d); hh.append(t)
            try:
                if exact_shanten(hh, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g) < s_now:
                    ok = True; break
            except Exception:
                continue
        if ok:
            out.append(t)
    return out


def _ww(h14, e, g, vis):
    """h14 = 摸完后的 14 张；返回"能弃成听牌时的最宽活等张"，否则 0。"""
    best = 0
    for d in sorted(set(h14)):
        rem = list(h14); rem.remove(d)
        try:
            if exact_shanten(rem, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g) != 0:
                continue
            w = waits(rem, exposed_melds=e, gangs=g)
        except Exception:
            continue
        live = sum(max(0, 4 - int((vis or {}).get(t, 0))) for t in w)
        if live > best: best = live
    return best


class SpeedC200(SpeedTUGC):
    K = 4
    BUDGET_MS = 400.0

    def __init__(self, name="speedc200"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        vis = None
        if view:
            try: vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
            except Exception: vis = None
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try: s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0), exposed_melds=exposed, gangs=gangs)
            except Exception: continue
            cands.append((d, rem, s))
        if not cands: return hand[0]
        smin = min(c[2] for c in cands)
        deadline = time.monotonic() + self.BUDGET_MS / 1000.0
        best_key, best_tile = None, None
        for d, rem, s in cands:
            if s != smin:
                continue
            if s == 0:
                try: wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
                except Exception: wcnt = 0
                key = (s, -wcnt, 0.0, 0.0, _pref(d, hand), -1 if d == drawn else 0)
                if best_key is None or key < best_key: best_key, best_tile = key, d
                continue
            # u1 = 真进张（活张数）——与 c135 同口径
            adv = _adv(rem, exposed, gangs, s)
            u1 = 0.0
            for t in adv:
                u1 += max(0, 4 - int((vis or {}).get(t, 0)))
            win2 = 0.0
            if time.monotonic() < deadline:
                adv.sort(key=lambda t: -(4 - int((vis or {}).get(t, 0))))
                for t in adv[:self.K]:
                    if time.monotonic() >= deadline: break
                    live = max(0, 4 - int((vis or {}).get(t, 0)))
                    h14 = list(rem); h14.append(t)
                    win2 += live * _ww(h14, exposed, gangs, vis)
            key = (s, 0, -u1, -win2, _pref(d, hand), -1 if d == drawn else 0)
            if best_key is None or key < best_key: best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
