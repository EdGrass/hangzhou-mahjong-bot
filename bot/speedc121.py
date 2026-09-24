# -*- coding: utf-8 -*-
"""C121 学生策略：C073-w4 弃牌 + **学到的副露判据**（在 C045 严格门控上做保守偏离）。

依据（2026-09-15 重放权威口径，300 房重建手牌）：
  我方窗口索取率 36.5%（speedtugc 141 房 +17.2/房），高胡率教师 42.2%；
  而「allow_equal」类松门控（speedtug/SpeedTU/speedtugh）索取率 57-60% → 真机 -25~-47/房。
  ⇒ 目标不是「多副露」，而是**把索取率从 36.5% 提到 ~42%**（教师水平）的选择性索取。
本策略只在「基线判过」的窗口上，按模型 p 的置信度补一小部分索取；默认不否决基线索取。
"""
from __future__ import annotations

import os

import numpy as np

from .c121meld import window_features
from .model import window_pending
from .speed import _chi_pairs, _melds_info
from .speedc068 import C068Policy
from .speedtugc import want_claim_strict_meld

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DISCARD = os.path.join(ROOT, "var", "c073_orig_w4_net.pt")
DEFAULT_MELD = os.path.join(ROOT, "var", "c121_meld_net.pt")
CHI_MAX = 2


class _MeldNet:
    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din=141):
                super().__init__()
                self.f = nn.Sequential(
                    nn.Linear(din, 256), nn.ReLU(), nn.Dropout(0.25),
                    nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.15),
                    nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))

            def forward(self, x):
                return self.f(x).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.net = Net(int(blob.get("din", 141)))
        self.net.load_state_dict(blob["state"])
        self.net.eval()
        self.mu = blob.get("mu")
        self.sd = blob.get("sd")

    def prob(self, rows):
        self.torch.set_num_threads(1)
        x = np.asarray(rows, dtype=np.float32)
        if self.mu is not None and self.sd is not None:
            x = (x - np.asarray(self.mu, dtype=np.float32)) / (np.asarray(self.sd, dtype=np.float32) + 1e-6)
        with self.torch.no_grad():
            logits = self.net(self.torch.tensor(x))
            return self.torch.sigmoid(logits).numpy()


class C121Policy(C068Policy):
    def __init__(self, name="speedc121", model_path=None, meld_path=None,
                 lo=0, hi=2, claim_p=0.60, veto_p=None, **kw):
        super().__init__(name=name, model_path=model_path or DEFAULT_DISCARD, lo=lo, hi=hi, **kw)
        self.claim_p = float(claim_p)
        self.veto_p = None if veto_p is None else float(veto_p)
        try:
            self.mnet = _MeldNet(meld_path or DEFAULT_MELD)
        except Exception:
            self.mnet = None

    def _p(self, view, kind, hand, melds, offer):
        if self.mnet is None:
            return None
        river = list(view.get("river") or [])
        am = view.get("all_melds") or []
        feat = window_features(hand, melds, river, am, offer, kind)
        try:
            return float(self.mnet.prob([feat])[0])
        except Exception:
            return None

    def decide(self, view):
        if not (window_pending(view) and view.get("offer_tile")) or self.mnet is None:
            return super().decide(view)
        offer = view.get("offer_tile")
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed, gangs = _melds_info(view)
        phase = view.get("phase")
        if phase == "response_peng":
            cnt = hand.count(offer)
            base_gang = cnt >= 3 and want_claim_strict_meld(view, "gang_ming")
            base_peng = cnt >= 2 and want_claim_strict_meld(view, "peng")
            p = self._p(view, "peng", hand, melds, offer)
            if base_gang:
                return {"action": "gang", "tile": offer}
            if base_peng:
                if self.veto_p is not None and p is not None and p < self.veto_p:
                    self.stats["meld_veto"] += 1
                    return {"action": "pass", "tile": ""}
                return {"action": "peng", "tile": offer}
            if p is not None and p >= self.claim_p and cnt >= 2:
                self.stats["meld_add"] += 1
                return {"action": "peng", "tile": offer}
            return {"action": "pass", "tile": ""}
        if phase == "response_chi":
            chi_cnt = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "chi")
            if len(hand) != 13 - 3 * exposed - gangs or chi_cnt >= CHI_MAX:
                return {"action": "pass", "tile": ""}
            pairs = _chi_pairs(hand, offer)
            if not pairs:
                return {"action": "pass", "tile": ""}
            base = any(want_claim_strict_meld(view, "chi", pair) for pair in pairs)
            p = self._p(view, "chi", hand, melds, offer)
            if base:
                if self.veto_p is not None and p is not None and p < self.veto_p:
                    self.stats["meld_veto"] += 1
                    return {"action": "pass", "tile": ""}
                return {"action": "chi", "tile": offer}
            if p is not None and p >= self.claim_p:
                self.stats["meld_add"] += 1
                return {"action": "chi", "tile": offer}
            return {"action": "pass", "tile": ""}
        return super().decide(view)
