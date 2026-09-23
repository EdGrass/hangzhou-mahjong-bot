# -*- coding: utf-8 -*-
"""SpeedC197 —— `speedc135` 的**单变量**候选：并列时再往前看**一步**（有界二步前瞻）。

背景（R519/R520）：
  - c135 已经在"最小向听组里按 **1 步真进张** u1 最大"选牌（真机最优命中 99.0%）。
  - 实测 **53.7%** 的未听牌弃牌决策里，**最大 u1 是并列的**（|best|=2/3/4 占 27.7/14.6/11.4%）
    ⇒ "二步信息"能影响超过一半的决策 ⇒ **这条轴有面**（不是 R505 那种 1% 面）。
  - 但 C048 的 rollout 版本太慢（8s/局）。本候选采用**有界**二步：
    只对**最小向听组**的候选、且只看它**活张最多的前 k 个进张**，估算"再下一步的最好进张"。

排序键（与 c135 的唯一差别就是第 3 项）：
    c135 : (s, -wcnt, -u1,            _pref, 保留摸切)
    c197 : (s, -wcnt, -(u1 + α·u2),   _pref, 保留摸切)
  - u2(d) = 对 rem(=H-d) 的**活张最多的前 k 张**进张 t，取 `best_u1(rem + t)` 的均值；
  - k(默认 3)、α(默认 1.0) 可调；`deadline` 保护：超时则退回纯 u1（决不拖过 3s 预算）。

口径：`best_u1` 与 c135 的 `_best_discard_realukeire` 用同一套（exact_shanten + real_ukeire + 同一可见集），
所以它测的是"同一个目标函数下，多看一步会不会更好"。
"""
from __future__ import annotations

import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .speedc135 import _best_discard_realukeire
from .speedtugc import SpeedTUGC
from .speedt import _pref
from .ukeire import real_ukeire, visible_counts

TILES = [t + s for s in ("w", "b", "t") for t in "123456789"] + ["东", "南", "西", "北", "中", "发", "白"]


def _advance_tiles(rem, e, g, vis, s_now):
    """rem 的进张（活张>0 且能把向听压下去）⇒ [(tile, live)]。"""
    out = []
    for t in TILES:
        live = 4 - int((vis or {}).get(t, 0))
        if live <= 0:
            continue
        ok = False
        for d in set(rem):
            hh = list(rem)
            hh.remove(d)
            hh.append(t)
            try:
                if exact_shanten(hh, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g) < s_now:
                    ok = True
                    break
            except Exception:
                continue
        if ok:
            out.append((t, live))
    return out


def _best_u1(hand, e, g, vis):
    """hand（14-3e-g 张，尚未弃牌）在最小向听组里的**最大真进张数**。"""
    cands = []
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
        except Exception:
            continue
        cands.append((d, rem, s))
    if not cands:
        return 0.0
    smin = min(c[2] for c in cands)
    best = 0.0
    for d, rem, s in cands:
        if s != smin:
            continue
        if s == 0:
            try:
                v = float(len(waits(rem, exposed_melds=e, gangs=g)))
            except Exception:
                v = 0.0
        else:
            try:
                v = float(real_ukeire(rem, exposed=e, gangs=g, visible=vis)[0] or 0)
            except Exception:
                v = 0.0
        if v > best:
            best = v
    return best


class SpeedC197(SpeedTUGC):
    K = 3
    ALPHA = 1.0
    BUDGET_MS = 300.0

    def __init__(self, name="speedc197"):
        super().__init__(name)

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        vis = None
        if view:
            try:
                vis = visible_counts(hand, river=view.get("river"), all_melds=view.get("all_melds"))
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
        deadline = time.monotonic() + self.BUDGET_MS / 1000.0
        best_key, best_tile = None, None
        for d, rem, s in cands:
            if s != smin:
                continue
            wcnt = 0
            u1 = 0.0
            if s == 0:
                try:
                    wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
                except Exception:
                    wcnt = 0
            else:
                try:
                    u1 = float(real_ukeire(rem, exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
                except Exception:
                    u1 = 0.0
            u2 = 0.0
            if s > 0 and time.monotonic() < deadline:
                try:
                    adv = _advance_tiles(rem, exposed, gangs, vis, s)
                    adv.sort(key=lambda x: -x[1])
                    adv = adv[:self.K]
                    if adv:
                        vals = []
                        for t, _live in adv:
                            if time.monotonic() >= deadline:
                                break
                            h14 = list(rem)
                            h14.append(t)
                            vals.append(_best_u1(h14, exposed, gangs, vis))
                        if vals:
                            u2 = sum(vals) / len(vals)
                except Exception:
                    u2 = 0.0
            # ★ 关键设计（R523）：**必须字典序**——u1 仍是第一键，u2 只在 u1 **完全并列**时生效。
            #   第一版写成 `(u1 + α·u2)` 会让"u1 略低但 u2 高"的牌反超 c135 ⇒ 实测把 c135 的 +3.23pp 打成 +0.85pp。
            #   正确形态只作用在 R520 测出的 **53.7% 并列集合**内部，不改变 c135 的既有选择。
            key = (s, -wcnt, -u1, -round(u2, 6), _pref(d, hand),
                   -1 if d == drawn else 0)
            if best_key is None or key < best_key:
                best_key, best_tile = key, d
        return best_tile if best_tile is not None else hand[0]
