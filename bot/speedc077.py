# -*- coding: utf-8 -*-
"""C077 学生策略：**行为克隆 + 状态价值** 混合打分。

score(候选) = BC_logit(候选) + λ · V_logit(候选)
  - BC  -> 「顶级会怎么选」（模仿信号，当前主力 c073_orig_w2 / c068_bc_lo0）
  - V   -> 「这个局面赢的概率」（结果信号，c076_value_net；验证分位赢率 7.4%→50.5%）
只有 (best - base) > margin 时才偏离 C045 基线；其余动作全部回退 C045。
"""
from __future__ import annotations

import os

import numpy as np

from mahjong.tiles import id_of
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speedc068 import C068Policy
from .speedc076 import _VNet
from .speedc067 import _Net, _best_discard_t, _pref
from .speedq2 import _state_feat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BC = os.path.join(ROOT, "var", "c073_orig_w2_net.pt")
DEFAULT_V = os.path.join(ROOT, "var", "c076_value_net.pt")


class C077Policy(C068Policy):
    def __init__(self, name="speedc077", model_path=None, value_path=None, lam=0.3,
                 margin=0.0, max_candidates=4, lo=0, hi=2):
        super().__init__(name=name, model_path=model_path or DEFAULT_BC,
                         margin=margin, max_candidates=max_candidates, lo=lo, hi=hi)
        self.lam = float(lam)
        try:
            self.vnet = _VNet(value_path or DEFAULT_V)
            self.value_path = value_path or DEFAULT_V
        except Exception:
            self.vnet = None
            self.value_path = None
        self.river_len = 0

    def _bc_features(self, hand, candidates, base, exposed, gangs):
        sb = ab = None
        rows = []
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            si = np.asarray(_state_feat(rem, exposed, gangs, use_ukeire=True), dtype=np.float32)
            ai = np.zeros(34, dtype=np.float32)
            ai[id_of(d)] = 1.0
            if d == base:
                sb, ab = si, ai
            rows.append((d, si, ai))
        if sb is None or ab is None:
            return None
        return [list(si) + list(ai) + [x - y for x, y in zip(si, sb)] +
                [x - y for x, y in zip(ai, ab)] for _d, si, ai in rows]

    def _v_features(self, hand, candidates, exposed, gangs):
        rl = float(self.river_len)
        out = []
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            out.append(list(_state_feat(rem, exposed, gangs, use_ukeire=True)) + [
                min(1.0, (rl / 4.0) / 12.0), min(1.0, rl / 24.0),
                exposed / 4.0, gangs / 4.0])
        return out

    def decide(self, view):
        if (self.model is None or self.vnet is None or not my_turn(view)
                or (window_pending(view) and view.get("offer_tile"))):
            return super().decide(view)
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        if len(hand) != 14 - 3 * exposed - gangs:
            return super().decide(view)
        from mahjong.hu import is_win
        try:
            if is_win(hand, exposed_melds=exposed, gangs=gangs) and drawn:
                return super().decide(view)
        except ValueError:
            pass
        if (view.get("god") or {}).get("catch_play") and drawn:
            return {"action": "discard", "tile": drawn}
        base = _best_discard_t(hand, drawn, exposed, gangs)
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs)
            except ValueError:
                continue
            cands.append((s, d))
        if not cands:
            return {"action": "discard", "tile": base}
        smin = min(s for s, _d in cands)
        if not (self.shanten_range[0] <= smin <= self.shanten_range[1]):
            return {"action": "discard", "tile": base}
        group = [d for s, d in cands if s == smin]
        others = sorted([d for d in group if d != base], key=lambda d: (_pref(d, hand), d))
        chosen = ([base] + others)[:self.max_candidates]
        if len(chosen) < 2:
            return {"action": "discard", "tile": base}
        self.river_len = len(view.get("river") or [])
        rows = self._bc_features(hand, chosen, base, exposed, gangs)
        if rows is None:
            return {"action": "discard", "tile": base}
        try:
            bc = [float(x) for x in self.model.score(rows)]
            vv = [float(x) for x in self.vnet.score(self._v_features(hand, chosen, exposed, gangs))]
        except Exception:
            return {"action": "discard", "tile": base}
        total = [b + self.lam * v for b, v in zip(bc, vv)]
        bi = chosen.index(base)
        besti = max(range(len(chosen)), key=lambda i: total[i])
        self.stats["used"] += 1
        if besti != bi and total[besti] > total[bi] + self.margin:
            self.stats["changed"] += 1
            return {"action": "discard", "tile": chosen[besti]}
        return {"action": "discard", "tile": base}
