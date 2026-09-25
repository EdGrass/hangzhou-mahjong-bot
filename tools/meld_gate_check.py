# -*- coding: utf-8 -*-
"""v3: gate verdict x outcome, with superseded windows removed.

A chi window never opens if another seat claims the discard first (peng/gang beats
chi), so a missing chi line is not necessarily a loss.  Peng windows are exclusive
(2 in our hand + 1 discarded leaves at most 1 elsewhere), so they cannot be
superseded.  READ-ONLY.
"""
from __future__ import annotations
import argparse, collections, glob, importlib.util, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ★ R1529：从 __file__ 推（原写死本机绝对路径 ⇒ clone 必崩）
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location('rm_gc3', os.path.join(ROOT, 'var', '_replay_model.py'))
RM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(RM)
ME = RM.ME
from bot.speed import _chi_pairs
from bot.speedc136 import _state, _after_best
from bot.ukeire import visible_counts
from bot.speedc151 import SpeedC151
ARM = SpeedC151()


def ubucket(du):
    if du < 0: return 'u<0'
    if du == 0: return 'u=0'
    if du <= 2: return 'u+1..2'
    if du <= 6: return 'u+3..6'
    return 'u>=+7'


ap = argparse.ArgumentParser()
ap.add_argument('--since', default='2026-09-20 14:54:07')
ap.add_argument('--limit', type=int, default=60)
ap.add_argument('--arm', default='speedc151')
ap.add_argument('--bai', default='any', choices=('any', 'yes', 'no'),
                help='窗口时刻我方手牌是否含白（财神）筛选')
a = ap.parse_args()
rooms = set()
for ln in io.open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
    ln = ln.strip()
    if not ln: continue
    try: d = json.loads(ln)
    except Exception: continue
    if (d.get('ts') or '') < a.since: continue
    if d.get('strategy') == a.arm: rooms.add(d['room'])
idx = RM.room_files()
files = []
for room in sorted(rooms):
    files += idx.get(room, [])
files = files[-a.limit:] if a.limit else files
T = collections.Counter()
for f in files:
    gid = os.path.basename(f)[:-5]
    dec = {}; dec_any = collections.Counter()
    for dl in glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', gid + '*.dec.jsonl')):
        for ln in io.open(dl, encoding='utf-8'):
            ln = ln.strip()
            if not ln: continue
            try: r = json.loads(ln)
            except Exception: continue
            p = r.get('p')
            if p not in ('response_peng', 'response_chi') or not r.get('o'): continue
            m = r.get('m') or []; h = r.get('h') or []
            if len(h) != 13 - 3 * len(m): continue
            if p == 'response_peng' and h.count(r['o']) < 2: continue
            dec.setdefault((p, r.get('t'), r['o'], tuple(sorted(h))),
                           (r.get('a') or {}).get('action'))
            dec_any[(p, r.get('t'), r['o'])] += 1
    try: recs = list(RM.iter_rounds([f]))
    except Exception: continue
    for rec in recs:
        me = rec['me']; river = []
        evs = list(rec['snapshots'])
        for i, (e, hands, melds, _dr) in enumerate(evs):
            t = e.get('type'); s = e.get('seat')
            if t == 'tile_discarded':
                tile = e.get('tile')
                if tile: river.append(tile)
                if isinstance(s, int) and s != me and tile:
                    h = list(hands[me]); mym = melds[me]
                    en = len(mym); gn = sum(1 for x in mym if x.get('type') == 'gang')
                    if len(h) == 13 - 3 * en - gn:
                        if h.count(tile) >= 2:
                            kind, pair = 'peng', None
                        elif (me - s) % 4 == 1 and _chi_pairs(h, tile):
                            kind, pair = 'chi', _chi_pairs(h, tile)[-1]
                        else:
                            kind = None
                        if kind:
                            if a.bai == 'yes' and '白' not in h:
                                kind = None
                            elif a.bai == 'no' and '白' in h:
                                kind = None
                        if kind:
                            vis = visible_counts(h, river=river, all_melds=[list(x) for x in melds])
                            sb = _state(h, en, gn, vis, True)
                            sa = _after_best(h, tile, kind, pair, en, gn, vis, True)
                            if sb is not None and sa is not None and sb[1] is not None and sa[1] is not None:
                                view = {'offer_tile': tile, 'my_hand': h, 'melds': mym,
                                        'river': list(river), 'all_melds': [list(x) for x in melds]}
                                try: gv = bool(ARM._want_claim(view, kind, pair))
                                except Exception: gv = False
                                act = dec.get(('response_%s' % kind, s, tile, tuple(sorted(h))))
                                cat = ('sh<0' if sa[0] - sb[0] < 0 else
                                       ('sh=0' if sa[0] == sb[0] else 'sh>0'))
                                b_ = ubucket(sa[1] - sb[1])
                                k = (cat, b_)
                                if not gv:
                                    T[(k, 'gate_no')] += 1
                                elif act in ('peng', 'chi'):
                                    T[(k, 'took')] += 1
                                elif act == 'gang':
                                    T[(k, 'gang')] += 1
                                elif act == 'pass':
                                    T[(k, 'gate_yes_but_pass')] += 1
                                else:
                                    # was it superseded by another seat's claim?
                                    sup = False
                                    for j in range(i + 1, min(i + 4, len(evs))):
                                        e2 = evs[j][0]
                                        if e2.get('type') in ('peng', 'chi', 'gang') and \
                                           e2.get('seat') != me and e2.get('tile') == tile:
                                            sup = True; break
                                    if sup:
                                        T[(k, 'superseded')] += 1
                                    else:
                                        T[(k, 'MISSED_ANSWER')] += 1
                                        if dec_any.get(('response_%s' % kind, s, tile)):
                                            T[(k, 'miss_with_row_stale_hand')] += 1
                                        else:
                                            T[(k, 'miss_no_row_at_all')] += 1
                                        # 服务端是否记了我们这一窗的超时？
                                        timed_out = False
                                        for j in range(i + 1, min(i + 4, len(evs))):
                                            e2 = evs[j][0]
                                            if e2.get('type') == 'timeout' and e2.get('seat') == me \
                                               and ((e2.get('data') or {}).get('kind') == 'response'):
                                                timed_out = True; break
                                        T[(k, 'miss_server_timeout' if timed_out else 'miss_no_timeout')] += 1
            elif t in ('peng', 'chi'):
                if s == me and e.get('tile') in river:
                    river.remove(e.get('tile'))
print('=' * 104)
print('gate verdict x outcome（60份；arm=%s；hand-keyed join；已扣被抢窗口）' % a.arm)
print('=' * 104)
print('%-7s %-9s | %6s | %6s | %6s | %9s | %8s | %10s' % (
    '向听', 'live进张', 'gate_no', 'took', 'gang', '被抢', 'gateYes-pass', 'MISSED'))
for cat in ('sh<0', 'sh=0', 'sh>0'):
    for b_ in ('u<0', 'u=0', 'u+1..2', 'u+3..6', 'u>=+7'):
        k = (cat, b_)
        g_no = T[(k, 'gate_no')]; took = T[(k, 'took')]; gang = T[(k, 'gang')]
        sup = T[(k, 'superseded')]; gp = T[(k, 'gate_yes_but_pass')]; miss = T[(k, 'MISSED_ANSWER')]
        n = g_no + took + gang + sup + gp + miss
        if not n: continue
        denom = took + gang + sup + gp + miss
        print('%-7s %-9s | %6d | %6d | %6d | %9d | %8d | %6d (%4.1f%%)' % (
            cat, b_, g_no, took, gang, sup, gp, miss, 100.0 * miss / max(1, denom)))
        if miss:
            print('        miss breakdown: no_row=%d  stale_hand=%d  server_timeout=%d  no_timeout=%d' % (
                T[(k, 'miss_no_row_at_all')], T[(k, 'miss_with_row_stale_hand')],
                T[(k, 'miss_server_timeout')], T[(k, 'miss_no_timeout')]))
    print('-' * 104)