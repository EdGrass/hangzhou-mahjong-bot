# -*- coding: utf-8 -*-
"""C067 学生策略：相对基线优势网络。

仅覆盖我的摸牌弃牌决策；胡、抓打圈、副露窗口全部回退 C045/SpeedTUGC。
学生输入 = [候选状态, 候选动作, 候选-基线状态差, 候选-基线动作差]。
模型缺失或局面不适合时零行为变化。
"""
from __future__ import annotations

import collections
import os

from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.tiles import counts_of, id_of

from .model import my_turn, window_pending
from .speedq2 import _state_feat
from .speedt import _best_discard_t, _pref
from .speedtugc import SpeedTUGC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c067_bc_net.pt")


class _Net:
    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din=154):
                super().__init__()
                self.f = nn.Sequential(
                    nn.Linear(din, 256), nn.ReLU(), nn.Dropout(0.15),
                    nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.10),
                    nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))

            def forward(self, x):
                return self.f(x).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.net = Net(int(blob.get("din", 154)))
        self.net.load_state_dict(blob["state"])
        self.net.eval()

    def score(self, rows):
        self.torch.set_num_threads(1)
        with self.torch.no_grad():
            return self.net(self.torch.tensor(rows, dtype=self.torch.float32)).numpy()


class C067Policy(SpeedTUGC):
    def __init__(self, name="speedc067", model_path=None, margin=0.0,
                 max_candidates=4, cand_order="pref"):
        super().__init__(name=name)
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        # 参与模型排序的「弃牌后向听」区间；默认只覆盖 1~2（抓打圈/听牌段交由 C045）
        self.shanten_range = (1, 2)
        # 候选排序键：pref = 旧的 _pref 序（已上线验证）；ukeire = 按弃后进张宽（覆盖教师选择更多）
        self.cand_order = str(cand_order or "pref")
        self.stats = collections.Counter()
        path = model_path or os.environ.get("HM_C067_MODEL") or DEFAULT_MODEL
        try:
            self.model = _Net(path)
            self.model_path = path
        except Exception:
            self.model = None
            self.model_path = None

    def _order_others(self, hand, group, base, view, pref_key):
        """候选排序钩子（默认=_pref/ukeire）；子类可用学到的排序器。"""
        return sorted([d for d in group if d != base], key=pref_key)

    def _score(self, rows):
        """打分钩子（默认=模型原始打分；子类可做 TTA/集成）。"""
        return self.model.score(rows)

    def _visible(self, view):
        """公开可见牌（弃牌河 + 四家副露）34 维计数；C067 不使用，返回 None。"""
        return None

    def _features(self, hand, candidates, base, exposed, gangs):
        sb = None
        ab = None
        rows = []
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            si = _state_feat(rem, exposed, gangs, use_ukeire=True)
            ai = [0.0] * 34
            ai[id_of(d)] = 1.0
            if d == base:
                sb, ab = si, ai
            rows.append((d, si, ai))
        if sb is None or ab is None:
            return None
        return [si + ai + [x - y for x, y in zip(si, sb)] +
                [x - y for x, y in zip(ai, ab)] for _d, si, ai in rows]

    def decide(self, view):
        if self.model is None or not my_turn(view) or (
                window_pending(view) and view.get("offer_tile")):
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
        if self.cand_order == "ukeire":
            from .c069routes import ukeire_counts

            def _key(d):
                rem = list(hand)
                rem.remove(d)
                neigh, live = ukeire_counts(rem)
                return (-live, -neigh, _pref(d, hand), d)
        else:
            def _key(d):
                return (_pref(d, hand), d)
        others = self._order_others(hand, group, base, view, _key)
        chosen = ([base] + others)[:self.max_candidates]
        if len(chosen) < 2:
            return {"action": "discard", "tile": base}
        self._vis = self._visible(view)
        rows = self._features(hand, chosen, base, exposed, gangs)
        if rows is None:
            return {"action": "discard", "tile": base}
        try:
            scores = self._score(rows)
        except Exception:
            self.stats["fallback"] += 1
            return {"action": "discard", "tile": base}
        bi = chosen.index(base)
        scores = [float(x) for x in scores]
        besti = max(range(len(chosen)), key=lambda i: scores[i])
        self.stats["used"] += 1
        if besti != bi and scores[besti] > scores[bi] + self.margin:
            self.stats["changed"] += 1
            return {"action": "discard", "tile": chosen[besti]}
        return {"action": "discard", "tile": base}