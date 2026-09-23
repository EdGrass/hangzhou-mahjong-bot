# -*- coding: utf-8 -*-
"""C070 学生策略：C068-lo0 弃牌模型 + 学到的副露（吃/碰）判据。

副露部分与 C045 的关系：以 C045 判据为基线，模型在「应/过」二选一上给出优势；
只有当模型选择与基线不同且分差 > meld_margin 时才改判。弃牌部分完全继承 C068-lo0。
"""
from __future__ import annotations

import collections
import os

import numpy as np

from mahjong.tiles import counts_of, id_of

from .c070meld import ROW_DIM, best_after_claim, rows_for_window
from .speedtw import _meld_tiles
from .model import window_pending
from .speed import _chi_pairs, _melds_info
from .speedc068 import C068Policy
from .speedtugc import want_claim_strict_meld

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MELD = os.path.join(ROOT, "var", "c070_meld_net.pt")
DEFAULT_DISCARD = os.path.join(ROOT, "var", "c068_bc_lo0_net.pt")


class _Net:
    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din=ROW_DIM, hidden=192):
                super().__init__()
                self.f = nn.Sequential(nn.Linear(din, hidden), nn.ReLU(), nn.Dropout(.15),
                                       nn.Linear(hidden, 96), nn.ReLU(), nn.Dropout(.1),
                                       nn.Linear(96, 48), nn.ReLU(), nn.Linear(48, 1))

            def forward(self, x):
                return self.f(x).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.net = Net(int(blob.get("din", ROW_DIM)))
        self.net.load_state_dict(blob["state"])
        self.net.eval()

    def score(self, rows):
        self.torch.set_num_threads(1)
        with self.torch.no_grad():
            return self.net(self.torch.tensor(np.asarray(rows, dtype=np.float32))).numpy()


class C070Policy(C068Policy):
    def __init__(self, name="speedc070", model_path=None, meld_path=None,
                 margin=0.0, max_candidates=4, lo=0, hi=2, meld_margin=0.0):
        super().__init__(name=name, model_path=model_path or DEFAULT_DISCARD,
                         margin=margin, max_candidates=max_candidates, lo=lo, hi=hi)
        self.meld_margin = float(meld_margin)
        self.meld_stats = collections.Counter()
        path = meld_path or os.environ.get("HM_C070_MODEL") or DEFAULT_MELD
        try:
            self.meld_model = _Net(path)
            self.meld_path = path
        except Exception:
            self.meld_model = None
            self.meld_path = None

    # ---------- 副露 ----------
    def _vis_seen(self, view, offer):
        seen = list(view.get("my_hand") or []).count(offer)
        seen += list(view.get("river") or []).count(offer)
        for seat_melds in (view.get("all_melds") or []):
            for m in (seat_melds or []):
                for t in _meld_tiles(m):
                    if t == offer:
                        seen += 1
        return float(seen)

    def _meld_rows(self, view, kind):
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        mc = np.asarray([sum(1 for m in melds if m.get("type") == "peng"),
                         sum(1 for m in melds if m.get("type") == "chi"),
                         sum(1 for m in melds if m.get("type") == "gang")], dtype=np.float32)
        offer = view.get("offer_tile")
        draws = list(view.get("river") or [])
        rows, base, ok = rows_for_window(
            hand, mc, offer, kind,
            draws=len(draws) / 4.0, river_len=len(draws),
            vis_offer=self._vis_seen(view, offer))
        return rows, base, ok, hand, offer, mc

    def _chi_best_pair(self, hand, offer, exposed, gangs):
        best = None
        for p in _chi_pairs(hand, offer):
            got = best_after_claim(hand, offer, "chi", p, exposed, gangs)
            if got is None:
                continue
            _rem, s, w, _d = got
            k = (s, -w)
            if best is None or k < best[0]:
                best = (k, p)
        return best[1] if best else None

    def decide(self, view):
        if (self.meld_model is not None and window_pending(view)
                and view.get("offer_tile") and view["seat"] >= 0):
            act = self._decide_meld(view)
            if act is not None:
                return act
        return super().decide(view)

    def _decide_meld(self, view):
        phase = view.get("phase") or ""
        if phase == "response_peng":
            kind = "peng"
        elif phase == "response_chi":
            kind = "chi"
        else:
            return None
        try:
            rows, base_idx, ok, hand, offer, mc = self._meld_rows(view, kind)
        except Exception:
            return None
        if not ok:
            return None
        exposed = int(mc[0] + mc[1] + mc[2]); gangs = int(mc[2])
        cnt = hand.count(offer)
        try:
            scores = [float(x) for x in self.meld_model.score(rows)]
        except Exception:
            self.meld_stats["fallback"] += 1
            return None
        self.meld_stats["windows"] += 1
        pick = 0 if scores[0] > scores[1] + self.meld_margin else 1
        if pick == base_idx:
            return None                      # 与基线一致 → 交给 C045 原逻辑
        self.meld_stats["changed"] += 1
        if pick == 1:
            return {"action": "pass", "tile": ""}
        # 模型倾向副露
        if kind == "peng":
            return {"action": "gang" if cnt >= 3 else "peng", "tile": offer}
        pair = self._chi_best_pair(hand, offer, exposed, gangs)
        if pair is None:
            return {"action": "pass", "tile": ""}
        return {"action": "chi", "tile": offer, "tiles": list(pair)}
