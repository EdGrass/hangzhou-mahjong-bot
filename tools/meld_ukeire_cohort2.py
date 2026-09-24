# -*- coding: utf-8 -*-
"""v2: cross shanten-delta with ukeire-delta when auditing meld acceptance.

Fix for the confound in tools/meld_ukeire_audit.py: `ukeire()` counts tiles that
lower shanten *from the hand's own shanten*, so a meld that RAISES shanten can show
a larger ukeire.  Only `delta_sh == 0` cells are interpretable as "same speed,
wider/narrower".  READ-ONLY.
"""
from __future__ import annotations
import argparse, collections, glob, importlib.util, json, os, ssl, sys, urllib.request
ROOT = r'D:\hangzhouMaj'
sys.path.insert(0, ROOT)
_s = importlib.util.spec_from_file_location('mua_c2', os.path.join(ROOT, 'tools', 'meld_ukeire_audit.py'))
mua = importlib.util.module_from_spec(_s); sys.modules['mua_c2'] = mua; _s.loader.exec_module(mua)
moa = mua.moa; ME = mua.ME; canon = mua.canon


def after_best(hand, tile, kind, ex, gg):
    """(shanten, live ukeire) of the BEST discard after taking this meld."""
    h = canon(hand, ex, gg)
    if kind == 'peng':
        if h.count(tile) < 2:
            return None
        h.remove(tile); h.remove(tile)
    else:
        p = moa._parse(tile)
        if not p or p[0] == 'h':
            return None
        suit, rank = p
        got = None
        for a, b in ((rank - 2, rank - 1), (rank - 1, rank + 1), (rank + 1, rank + 2)):
            ta, tb = '%d%s' % (a, suit), '%d%s' % (b, suit)
            if a < 1 or b > 9 or h.count(ta) < 1 or h.count(tb) < 1:
                continue
            hh = list(h); hh.remove(ta); hh.remove(tb); got = hh; break
        if got is None:
            return None
        h = got
    best = None
    for t in sorted(set(h)):
        hh = list(h); hh.remove(t)
        v = moa.ukeire(hh, ex + 1, gg)
        if v is None:
            continue
        s = moa.sh(hh, ex + 1, gg)
        key = (9 if s is None else s, -(v or 0))
        if best is None or key < best[0]:
            best = (key, s, v)
    if best is None:
        return None
    return best[1], best[2]


def board_top(n=32):
    try:
        ck = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
        req = urllib.request.Request('https://10.240.169.190:18080/portal/api/leaderboard?period=all',
                                     headers={'Cookie': ck})
        d = json.loads(urllib.request.urlopen(req, timeout=25,
                      context=ssl._create_unverified_context()).read().decode('utf-8'))
        return {p['user_id'] for p in (d.get('top') or [])[:n]}
    except Exception as e:
        print('WARN top32 fetch failed:', e)
        return set()


def ubucket(d):
    if d <= -7: return 'u<=-7'
    if d < 0: return 'u-1..-6'
    if d == 0: return 'u=0'
    if d <= 2: return 'u+1..2'
    if d <= 6: return 'u+3..6'
    return 'u>=+7'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', default='recent')
    ap.add_argument('--limit', type=int, default=100)
    ap.add_argument('--max-turn', type=int, default=3)
    a = ap.parse_args()
    top = board_top(32)
    files = []
    for dd in [x.strip() for x in a.dirs.split(',') if x.strip()]:
        files += glob.glob(os.path.join(ROOT, 'var', 'replays', dd, '*.json'))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]
    # stat[sh_cat][ubucket][cohort] = [offers, takes]
    stat = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(lambda: [0, 0])))
    used = 0
    for p in files:
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        ids = [(s.get('user_id') or '') for s in (d.get('seats') or [])]
        if ME not in ids or len(ids) != 4:
            continue
        used += 1
        me = ids.index(ME)
        coh = ['me' if i == me else ('top' if u in top else 'oth') for i, u in enumerate(ids)]
        hands = [None] * 4; nm = [0] * 4; ng = [0] * 4; turn = [0] * 4; pending = {}
        for b in d.get('blocks') or []:
            sh0 = b.get('start_hands')
            if sh0 and any(isinstance(x, (list, tuple)) for x in sh0):
                hands = [list(x) if isinstance(x, (list, tuple)) else [] for x in sh0]
                nm = [0] * 4; ng = [0] * 4; turn = [0] * 4; pending = {}
            if hands[0] is None:
                continue
            for e in b.get('events') or []:
                t, s = e.get('type'), e.get('seat')
                if t == 'round_ended':
                    hands = [None] * 4; pending = {}; continue
                if s is None or s < 0 or hands[s] is None:
                    continue
                if t == 'tile_drawn':
                    hands[s].append(e.get('tile'))
                elif t == 'tile_discarded':
                    tile = e.get('tile')
                    for o in range(4):
                        if o == s or hands[o] is None or turn[o] >= a.max_turn:
                            continue
                        ex, gg = nm[o] + ng[o], ng[o]
                        h0 = canon(hands[o], ex, gg)
                        sh_b = moa.sh(h0, ex, gg)
                        u_b = moa.ukeire(h0, ex, gg)
                        if sh_b is None or u_b is None:
                            continue
                        cands = [after_best(hands[o], tile, k, ex, gg) for k in ('peng', 'chi')]
                        cands = [c for c in cands if c is not None and c[0] is not None and c[1] is not None]
                        if not cands:
                            continue
                        sh_a, u_a = min(cands, key=lambda c: (c[0], -c[1]))
                        dsh = sh_a - sh_b
                        cat = 'sh<0' if dsh < 0 else ('sh=0' if dsh == 0 else 'sh>0')
                        b_ = ubucket(u_a - u_b)
                        stat[cat][b_][coh[o]][0] += 1
                        pending[o] = (cat, b_, coh[o])
                    if tile in hands[s]:
                        hands[s].remove(tile)
                    turn[s] += 1; pending.pop(s, None)
                elif t in ('pass', 'timeout'):
                    pending.pop(s, None)
                elif t in ('peng', 'chi'):
                    if s in pending:
                        cat, b_, co = pending.pop(s); stat[cat][b_][co][1] += 1
                    if t == 'peng':
                        for _ in range(2):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))
                        nm[s] += 1
                    else:
                        usedt = list((e.get('data') or {}).get('tiles') or [])
                        if e.get('tile') in usedt:
                            usedt.remove(e.get('tile'))
                        for x in usedt:
                            if x in hands[s]:
                                hands[s].remove(x)
                        nm[s] += 1
                elif t == 'gang':
                    kind = (e.get('data') or {}).get('kind')
                    if kind == 'bu':
                        if e.get('tile') in hands[s]:
                            hands[s].remove(e.get('tile'))
                        nm[s] -= 1; ng[s] += 1
                    else:
                        for _ in range(4 if kind == 'an' else 3):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))
                        ng[s] += 1
    print('=' * 104)
    print('吃/碰 接受率：向听变化 x 进张变化（语料 %d 份可用/%d；前 %d 巡；top32=%d）'
          % (used, len(files), a.max_turn, len(top)))
    print('=' * 104)
    print('%-8s %-10s | %-21s | %-21s | %-21s' % ('向听', '进张', 'me offer/take%', 'top32 offer/take%', 'oth offer/take%'))
    order = ['sh<0', 'sh=0', 'sh>0']
    ubs = ['u<=-7', 'u-1..-6', 'u=0', 'u+1..2', 'u+3..6', 'u>=+7']
    for cat in order:
        for b_ in ubs:
            cells = []
            any_n = False
            for co in ('me', 'top', 'oth'):
                n, k = stat[cat][b_].get(co, [0, 0])
                any_n = any_n or n > 0
                cells.append('%5d / %5.1f%%' % (n, 100.0 * k / n if n else 0.0))
            if any_n:
                print('%-8s %-10s | %-21s | %-21s | %-21s' % (cat, b_, cells[0], cells[1], cells[2]))
        print('-' * 104)


main()