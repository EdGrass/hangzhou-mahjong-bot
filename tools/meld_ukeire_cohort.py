# -*- coding: utf-8 -*-
"""吃/碰进张增益接受率 —— 按 cohort (me / top32 / oth) 分层。READ-ONLY.
复用 tools/meld_ukeire_audit.py 的 uke_after_one / canon / moa，不修改任何既有文件。
"""
from __future__ import annotations
import argparse, collections, glob, importlib.util, json, os, ssl, sys, urllib.request
ROOT = r'D:\hangzhouMaj'
sys.path.insert(0, ROOT)
_s = importlib.util.spec_from_file_location('mua_c', os.path.join(ROOT, 'tools', 'meld_ukeire_audit.py'))
mua = importlib.util.module_from_spec(_s); sys.modules['mua_c'] = mua; _s.loader.exec_module(mua)
moa = mua.moa; ME = mua.ME; canon = mua.canon; uke_after_one = mua.uke_after_one


def board_top(n=32):
    try:
        ck = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
        req = urllib.request.Request('<平台地址>/portal/api/leaderboard?period=all',
                                     headers={'Cookie': ck})
        d = json.loads(urllib.request.urlopen(req, timeout=25,
                      context=ssl._create_unverified_context()).read().decode('utf-8'))
        return {p['user_id'] for p in (d.get('top') or [])[:n]}
    except Exception as e:
        print('WARN top32 fetch failed:', e)
        return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', default='recent')
    ap.add_argument('--limit', type=int, default=30)
    ap.add_argument('--max-turn', type=int, default=3)
    a = ap.parse_args()
    top = board_top(32)
    files = []
    for dd in [x.strip() for x in a.dirs.split(',') if x.strip()]:
        files += glob.glob(os.path.join(ROOT, 'var', 'replays', dd, '*.json'))
    files = sorted(set(files))
    if a.limit:
        files = files[-a.limit:]
    stat = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for p in files:
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        ids = [(s.get('user_id') or '') for s in (d.get('seats') or [])]
        if ME not in ids or len(ids) != 4:
            continue
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
                        if moa.sh(list(hands[o]), ex, gg) is None:
                            continue
                        h = canon(hands[o], ex, gg)
                        base_u = moa.ukeire(h, ex, gg)
                        ups = [v for v in (uke_after_one(hands[o], tile, 'peng', ex, gg),
                                           uke_after_one(hands[o], tile, 'chi', ex, gg)) if v is not None]
                        if base_u is None or not ups:
                            continue
                        delta = max(ups) - base_u
                        bucket = ('same_or_narrower' if delta <= 0 else
                                  ('wider_1_2' if delta <= 2 else
                                   ('wider_3_6' if delta <= 6 else 'wider_7plus')))
                        stat[bucket][coh[o]][0] += 1
                        pending[o] = (bucket, coh[o])
                    if tile in hands[s]:
                        hands[s].remove(tile)
                    turn[s] += 1; pending.pop(s, None)
                elif t in ('pass', 'timeout'):
                    pending.pop(s, None)
                elif t in ('peng', 'chi'):
                    if s in pending:
                        bucket, co = pending.pop(s); stat[bucket][co][1] += 1
                    if t == 'peng':
                        for _ in range(2):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))
                        nm[s] += 1
                    else:
                        used = list((e.get('data') or {}).get('tiles') or [])
                        if e.get('tile') in used:
                            used.remove(e.get('tile'))
                        for x in used:
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
    print('=' * 92)
    print('吃/碰 进张增益接受率（语料 %d 份；前 %d 巡；top32 标记数=%d）' % (len(files), a.max_turn, len(top)))
    print('-' * 92)
    print('%-16s | %-24s | %-24s | %-24s' % ('档位', 'me offer / take%', 'top32 offer / take%', 'oth offer / take%'))
    names = {'wider_7plus': '进张+7以上', 'wider_3_6': '进张+3~6',
             'wider_1_2': '进张+1~2', 'same_or_narrower': '进张<=0'}
    for b in ('wider_7plus', 'wider_3_6', 'wider_1_2', 'same_or_narrower'):
        cells = []
        for co in ('me', 'top', 'oth'):
            n, k = stat[b].get(co, [0, 0])
            cells.append('%5d / %5.1f%%' % (n, 100.0 * k / n if n else 0.0))
        print('%-16s | %-24s | %-24s | %-24s' % (names[b], cells[0], cells[1], cells[2]))
    print('=' * 92)


main()