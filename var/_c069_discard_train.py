# -*- coding: utf-8 -*-
"""C069 弃牌模型：在 C068-lo0（最小向听候选内排序）基础上，加入**目标牌型（route）特征**。

动机：番值由分支倍率决定（平胡×1 / 七对×2 / 豪华七对 2^(n+1)，再叠 4白/爆头/链），
而现有弃牌权重是路线无关的单一偏好表。本模型让网络显式看到「弃牌后各条路线的进度」：
七对向听/对数/四张组、爆头达成、四白进度、清一色集中度、一般形向听/进张。

特征（每候选 65 维）= 在线 _state_feat(43) + c069routes.route_feats(22)
行向量 = [候选特征, 候选动作 onehot34, 候选-基线差65, 动作差34] → din = 198
"""
from __future__ import annotations
import argparse, os, sys, collections, pickle
import numpy as np, torch, torch.nn as nn
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from mahjong.tiles import ID_TILES, id_of
from mahjong.shanten_exact import shanten as S
from bot.c069routes import route_feats, ROUTE_DIM
from bot.speedq2 import _state_feat
from bot.speedt import _pref

TILES = [ID_TILES[i] for i in range(33)] + ['白']
FDIM = 43 + ROUTE_DIM
DIN = FDIM * 2 + 68


class Net(nn.Module):
    def __init__(self, din=DIN, hidden=256):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(din, hidden), nn.ReLU(), nn.Dropout(.15),
                               nn.Linear(hidden, 128), nn.ReLU(), nn.Dropout(.1),
                               nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x):
        return self.f(x).squeeze(-1)


def feat(hand, d, e, g):
    """候选弃牌 d 的特征：在线 _state_feat + 路线特征（训练/在线严格同源）。"""
    rem = list(hand)
    rem.remove(d)
    return list(_state_feat(rem, e, g, use_ukeire=True)) + list(route_feats(rem, e, g))


def build(d, lo=0, hi=2, max_cand=4, stat=None):
    X = d['X']; Y = d['Y']; BASE = d['BASE']
    groups = []
    for i in range(len(X)):
        hand = [TILES[j] for j in range(34) for _ in range(int(round(float(X[i, j]))))]
        e = int(X[i, 34] + X[i, 35] + X[i, 36]); g = int(X[i, 36])
        vals = []
        for d0 in sorted(set(hand)):
            r = list(hand); r.remove(d0)
            try:
                s = S(r, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
            except Exception:
                continue
            vals.append((s, d0))
        if not vals:
            continue
        sm = min(v for v, _ in vals)
        if not (lo <= sm <= hi):
            if stat is not None: stat['skip_shanten'] += 1
            continue
        cand = [d0 for v, d0 in vals if v == sm]
        y = TILES[int(Y[i])]
        if y not in cand or len(cand) < 2:
            if stat is not None: stat['skip_label'] += 1
            continue
        ba = TILES[int(BASE[i])] if int(BASE[i]) >= 0 else cand[0]
        if ba not in cand:
            ba = cand[0]
        others = sorted([x for x in cand if x != ba], key=lambda x: (_pref(x, hand), x))
        chosen = ([ba] + others)[:max(2, int(max_cand))]
        if y not in chosen:
            if stat is not None: stat['skip_trunc'] += 1
            continue
        fs = [np.asarray(feat(hand, d0, e, g), dtype=np.float32) for d0 in chosen]
        one = [np.eye(34, dtype=np.float32)[id_of(d0)] for d0 in chosen]
        fi = chosen.index(y); bi = chosen.index(ba)
        rows = [np.concatenate([fs[k], one[k], fs[k] - fs[bi], one[k] - one[bi]])
                for k in range(len(chosen))]
        groups.append((np.asarray(rows, np.float32), fi, sm, bi))
        if stat is not None:
            stat['kept'] += 1; stat['shanten%d' % sm] += 1
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='var/_bc_data_c068.npz')
    ap.add_argument('--cache', default='var/_c069_groups.pkl')
    ap.add_argument('--out', default='var/c069_bc_net.pt')
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--epochs', type=int, default=60)
    ap.add_argument('--lr', type=float, default=8e-4)
    ap.add_argument('--seed', type=int, default=31)
    ap.add_argument('--hidden', type=int, default=256)
    ap.add_argument('--lo', type=int, default=0); ap.add_argument('--hi', type=int, default=2)
    ap.add_argument('--max-candidates', type=int, default=4)
    ap.add_argument('--val-frac', type=float, default=0.2)
    a = ap.parse_args()
    torch.set_num_threads(1); torch.manual_seed(a.seed); np.random.seed(a.seed)
    d = np.load(a.data, allow_pickle=True)
    if os.path.exists(a.cache) and not a.rebuild:
        groups = pickle.load(open(a.cache, 'rb')); print('loaded cache', a.cache, flush=True)
    else:
        stat = collections.Counter(); groups = build(d, a.lo, a.hi, a.max_candidates, stat)
        pickle.dump(groups, open(a.cache, 'wb')); print('built', dict(stat), flush=True)
    cut = int(len(groups) * (1.0 - a.val_frac)); tr, va = groups[:cut], groups[cut:]
    print('groups', len(groups), 'train', len(tr), 'val', len(va), 'din', DIN, flush=True)
    net = Net(DIN, a.hidden); opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-5)

    def loss_batch(gs):
        logits = net(torch.cat([torch.tensor(g[0]) for g in gs])); loss = 0.; off = 0
        for g in gs:
            n = len(g[0]); loss = loss + nn.functional.cross_entropy(logits[off:off + n], torch.tensor(g[1])); off += n
        return loss / max(1, len(gs))

    def eval_set(gs):
        ok = base = 0; bys = collections.Counter(); nbys = collections.Counter()
        with torch.no_grad():
            for g in gs:
                logits = net(torch.tensor(g[0])); hit = int(int(torch.argmax(logits)) == g[1])
                ok += hit; base += int(g[1] == g[3]); bys[g[2]] += hit; nbys[g[2]] += 1
        return ok / max(1, len(gs)), base / max(1, len(gs)), {k: '%.3f(%d)' % (bys[k] / nbys[k], nbys[k]) for k in sorted(nbys)}

    best = -1; bestby = {}
    for ep in range(1, a.epochs + 1):
        net.train(); order = np.random.RandomState(a.seed + ep).permutation(len(tr)); tot = 0; nb = 0
        for i in range(0, len(order), 512):
            gs = [tr[j] for j in order[i:i + 512]]; opt.zero_grad(); l = loss_batch(gs); l.backward(); opt.step()
            tot += float(l.item()); nb += 1
        net.eval(); ac, ba, by = eval_set(va)
        if ac > best:
            best = ac
            torch.save({'state': net.state_dict(), 'din': DIN, 'top_acc': float(ac), 'base_acc': float(ba),
                        'data': os.path.basename(a.data), 'feat': 'route22', 'lo': a.lo, 'hi': a.hi,
                        'max_candidates': a.max_candidates}, a.out)
            bestby = by
        if ep % 5 == 0 or ep == 1:
            print('ep=%02d loss=%.4f val_top=%.4f val_base=%.4f by=%s' % (ep, tot / max(1, nb), ac, ba, by), flush=True)
    print('best_top=%.4f saved=%s by=%s' % (best, a.out, bestby), flush=True)


if __name__ == '__main__':
    main()
