# -*- coding: utf-8 -*-
"""爆头可达性评估器（值函数）的**在线接口**。特征定义必须与 `var/_baotou_dataset.py` 逐项一致。"""
from __future__ import annotations
import collections, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import torch
import torch.nn as nn
from mahjong.shanten_exact import shanten as SH
from bot.ukeire import real_ukeire, visible_counts

_MODEL = None

def _net(nfeat):
    return nn.Sequential(nn.Linear(nfeat, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

def load(path=None):
    global _MODEL
    if _MODEL is None:
        d = torch.load(path or os.path.join(ROOT, "var", "baotou_v1.pt"), map_location="cpu", weights_only=False)
        n = _net(d["nfeat"]); n.load_state_dict(d["sd"]); n.eval()
        _MODEL = (n, d["mu"], d["sd_"])
    return _MODEL

def features(h13, exposed, gangs, river, all_melds, god, draw_idx, vis=None):
    """h13 = **弃牌后**的 13-3e-g 张；返回 14 维特征（与训练时同序）。"""
    cnt = collections.Counter(h13)
    pairs = sum(1 for k, v in cnt.items() if v >= 2)
    adj = 0
    for suit in "wbt":
        for i in range(1, 9):
            if (str(i) + suit) in cnt and (str(i + 1) + suit) in cnt:
                adj += 1
    iso = 0
    for k, v in cnt.items():
        if k in "东南西北中发白":
            if v == 1: iso += 1
            continue
        if v >= 2: continue
        try: n = int(k[0]); s = k[1]
        except Exception: continue
        if not any((str(n + dd) + s) in cnt for dd in (-2, -1, 1, 2) if 1 <= n + dd <= 9):
            iso += 1
    try: s = SH(list(h13), qidui=(exposed == 0 and gangs == 0), exposed_melds=exposed, gangs=gangs)
    except Exception: s = 9
    if vis is None:
        try: vis = visible_counts(h13, river=river, all_melds=all_melds)
        except Exception: vis = None
    u1 = 0.0
    try: u1 = float(real_ukeire(list(h13), exposed=exposed, gangs=gangs, visible=vis)[0] or 0)
    except Exception: pass
    god = god or {}
    # ★ R568：**去掉 draw_idx**（它与 river_len 冗余；训练用真实巡目、推理曾写死 0 ⇒ 口径错位）
    return [s, cnt.get("白", 0), pairs, adj, iso, len(h13), exposed + gangs,
            len(river or []), u1, int(bool(god.get("baotou"))), int(god.get("chain_count") or 0),
            int(god.get("piao_count") or 0), int(bool(god.get("catch_play")))]

def value_from_features(fv):
    net, mu, sd = load()
    x = torch.tensor([[(float(a) - float(b)) / float(c) for a, b, c in zip(fv, mu, sd)]], dtype=torch.float32)
    with torch.no_grad():
        return float(torch.sigmoid(net(x)).item())

def value(h13, exposed, gangs, river, all_melds, god, draw_idx, vis=None):
    return value_from_features(features(h13, exposed, gangs, river, all_melds, god, draw_idx, vis))

