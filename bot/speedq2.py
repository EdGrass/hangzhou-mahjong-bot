# -*- coding: utf-8 -*-
"""C064 快速价值策略：用离线动作条件 MLP 对同向听弃牌做保守重排。

模型输入 = 43 维状态特征（含有效进张代理）+ 34 维动作 one-hot；双头输出
本局胡/听概率。在线只做一次小批量 MLP 推理，不进行 rollout；模型缺失或
局面不适合时 100% 回退 C045/SpeedTUGC。

2026-09-13 门禁结论：145k on-policy 样本、按整局切分验证 AUC≈0.680；
5 seed ×4 房快筛代理 −0.044、房均分 −1.0、胡率 −2.5pp。
C065 配对多分支（K=2：10,422 候选行 / 20,844 分支 run）pairwise
RankNet 成对排序准确率 0.513；s=2-only 首批 5×8 代理 +0.022，但独立
5×8 复核代理 −0.006、房均分 +0.2。K=4（41,688 分支 run）排序准确率
反而降到 0.482，3×4 快筛代理 +0.010，扩展无收益。
**未晋级生产，未注册到 run_bot.py；C045 仍是唯一默认竞技策略。**
"""
from __future__ import annotations

import collections
import os

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.tiles import counts_of, id_of, is_suit_tile, suit_and_num

from .model import my_turn, window_pending
from .speedt import _best_discard_t, _pref
from .speedtugc import SpeedTUGC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c065_pair_net.pt")


class _Net:
    """延迟加载 torch，避免未使用该策略时增加启动成本。"""

    def __init__(self, path):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self, din):
                super().__init__()
                self.trunk = nn.Sequential(
                    nn.Linear(din, 256), nn.ReLU(), nn.Dropout(0.15),
                    nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.10),
                    nn.Linear(128, 64), nn.ReLU(),
                )
                self.hu = nn.Linear(64, 1)
                self.tp = nn.Linear(64, 1)

            def forward(self, x):
                z = self.trunk(x)
                return self.hu(z).squeeze(-1), self.tp(z).squeeze(-1)

        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.torch = torch
        self.din = int(blob.get("din", 75))
        self.net = Net(self.din)
        self.net.load_state_dict(blob["state"])
        self.net.eval()

    def score(self, feat_rows):
        self.torch.set_num_threads(1)
        with self.torch.no_grad():
            x = self.torch.tensor(feat_rows, dtype=self.torch.float32)
            hu, tp = self.net(x)
            return (self.torch.sigmoid(hu).numpy(),
                    self.torch.sigmoid(tp).numpy())


def _ukeire_proxy(hand13):
    neigh = set(hand13)
    for tile in set(hand13):
        try:
            idx = id_of(tile)
        except ValueError:
            continue
        if is_suit_tile(idx):
            suit, num = suit_and_num(idx)
            for delta in (-2, -1, 1, 2):
                n = num + delta
                if 1 <= n <= 9:
                    neigh.add("%d%s" % (n, "wbt"[suit]))
    neigh.add("白")
    live = sum(max(0, 4 - hand13.count(t)) for t in neigh)
    return float(len(neigh)), float(live)


def _state_feat(hand13, exposed, gangs, use_ukeire=True):
    c = collections.Counter(hand13)
    pairs = sum(v // 2 for k, v in c.items() if k != "白")
    try:
        s = exact_shanten(hand13, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        w = len(waits(hand13, exposed_melds=exposed, gangs=gangs)) if s == 0 else 0
    except ValueError:
        s, w = 4, 0
    base = [x / 4.0 for x in counts_of(hand13)] + [
        float(exposed), float(gangs), float(s), 5.0, float(pairs),
        float(c.get("白", 0)), float(w),
    ]
    if use_ukeire:
        base.extend(_ukeire_proxy(hand13))
    return base


class _Ensemble:
    def __init__(self, nets):
        self.nets = list(nets)
        self.din = nets[0].din if nets else 75

    def score(self, feat_rows):
        hs, ts = [], []
        for net in self.nets:
            h, t = net.score(feat_rows)
            hs.append(h)
            ts.append(t)
        import numpy as np
        return np.mean(hs, axis=0), np.mean(ts, axis=0)


class SpeedQ2(SpeedTUGC):
    def __init__(self, name="speedq2", model_path=None, margin=0.05,
                 max_candidates=4, tp_weight=0.0, allowed_shanten=(2,)):
        super().__init__(name=name)
        self.margin = float(margin)
        self.max_candidates = max(2, int(max_candidates))
        self.tp_weight = float(tp_weight)
        self.allowed_shanten = tuple(sorted(set(int(x) for x in allowed_shanten)))
        self.stats = collections.Counter()
        raw = model_path or os.environ.get("HM_C064_MODEL") or DEFAULT_MODEL
        paths = [x.strip() for x in str(raw).split(",") if x.strip()]
        nets = []
        for path in paths:
            try:
                nets.append(_Net(path))
            except Exception:
                pass
        self.model = _Ensemble(nets) if nets else None
        self.model_path = ",".join(paths) if nets else None

    def _scores(self, hand, candidates, exposed, gangs):
        rows = []
        use_ukeire = bool(getattr(self.model, "din", 77) >= 77)
        for d in candidates:
            rem = list(hand)
            rem.remove(d)
            feat = _state_feat(rem, exposed, gangs, use_ukeire=use_ukeire)
            onehot = [0.0] * 34
            onehot[id_of(d)] = 1.0
            rows.append(feat + onehot)
        ph, pt = self.model.score(rows)
        return {d: float(ph[i]) + self.tp_weight * float(pt[i])
                for i, d in enumerate(candidates)}

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
        group = [d for s, d in cands if s == smin]
        if smin not in self.allowed_shanten or len(group) < 2:
            return {"action": "discard", "tile": base}
        # C045 基线永远优先进入评分集；其余按静态弃牌键排序。
        others = sorted([d for d in group if d != base],
                        key=lambda d: (_pref(d, hand), d))
        group = ([base] * (base in hand) + others)[:self.max_candidates]
        if base not in group:
            group[-1] = base
        try:
            scores = self._scores(hand, group, exposed, gangs)
        except Exception:
            self.stats["fallback"] += 1
            return {"action": "discard", "tile": base}
        best = max(group, key=lambda d: scores[d])
        self.stats["used"] += 1
        if scores[best] > scores[base] + self.margin:
            self.stats["changed"] += 1
            return {"action": "discard", "tile": best}
        return {"action": "discard", "tile": base}