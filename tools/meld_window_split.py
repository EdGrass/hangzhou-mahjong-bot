# -*- coding: utf-8 -*-
"""v2: ONE row per (round, discarder, tile) window we could claim.

Fix vs v1: (a) a single row per window (peng has priority, chi only if peng is not
legal) instead of one row per (kind, pair); (b) the decision-log join applies the
same content filter as the validated capture tools; (c) reports the live-ukeire
bucket from the arm's OWN metric.  READ-ONLY.
"""
from __future__ import annotations
import argparse, collections, glob, importlib.util, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ★ R1529：从 __file__ 推（原写死本机绝对路径 ⇒ clone 必崩）
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location('rm_ws2', os.path.join(ROOT, 'var', '_replay_model.py'))
RM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(RM)
ME = RM.ME
from bot.speed import _chi_pairs
from bot.speedc136 import _state, _after_best
from bot.ukeire import visible_counts


def ubucket(du):
    if du < 0: return 'u<0'
    if du == 0: return 'u=0'
    if du <= 2: return 'u+1..2'
    if du <= 6: return 'u+3..6'
    return 'u>=+7'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2026-09-20 14:54:07')
    ap.add_argument('--limit', type=int, default=60)
    ap.add_argument('--arm', default='speedc151')
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
    stat = collections.defaultdict(collections.Counter)
    used = 0
    for f in files:
        gid = os.path.basename(f)[:-5]
        dec = {}
        for dl in glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', gid + '*.dec.jsonl')):
            for ln in io.open(dl, encoding='utf-8'):
                ln = ln.strip()
                if not ln: continue
                try: r = json.loads(ln)
                except Exception: continue
                p = r.get('p')
                if p not in ('response_peng', 'response_chi') or not r.get('o'): continue
                m = r.get('m') or []; h = r.get('h') or []
                if len(h) != 13 - 3 * len(m): continue          # validated content filter
                if p == 'response_peng' and h.count(r['o']) < 2: continue
                dec.setdefault((p, r.get('t'), r['o'], tuple(sorted(h))), ((r.get('a') or {}).get('action'), p))
        try: recs = list(RM.iter_rounds([f]))
        except Exception: continue
        used += 1
        for rec in recs:
            me = rec['me']; river = []
            for e, hands, melds, _dr in rec['snapshots']:
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
                                vis = visible_counts(h, river=river, all_melds=[list(x) for x in melds])
                                sb = _state(h, en, gn, vis, True)
                                sa = _after_best(h, tile, kind, pair, en, gn, vis, True)
                                if sb is not None and sa is not None and sb[1] is not None and sa[1] is not None:
                                    dsh = sa[0] - sb[0]
                                    cat = 'sh<0' if dsh < 0 else ('sh=0' if dsh == 0 else 'sh>0')
                                    b_ = ubucket(sa[1] - sb[1])
                                    got = dec.get(('response_%s' % kind, s, tile, tuple(sorted(h))))
                                    c = stat[(cat, b_)]
                                    c['n'] += 1
                                    if got is None:
                                        c['missing'] += 1
                                    else:
                                        act = got[0]
                                        if act in ('peng', 'chi'):
                                            c['take'] += 1
                                        else:
                                            c['pass'] += 1
                elif t in ('peng', 'chi'):
                    if s == me and e.get('tile') in river:
                        river.remove(e.get('tile'))
    print('=' * 96)
    print('我方副露窗口（一事件一行）x live进张（语料 %d 份；arm=%s）' % (used, a.arm))
    print('=' * 96)
    print('%-7s %-9s | %6s | %9s | %9s | %9s | %9s' % ('向听', 'live进张', 'n', '作答%', '接受%', 'pass%', '未作答%'))
    for cat in ('sh<0', 'sh=0', 'sh>0'):
        for b_ in ('u<0', 'u=0', 'u+1..2', 'u+3..6', 'u>=+7'):
            c = stat[(cat, b_)]
            n = c['n']
            if not n: continue
            print('%-7s %-9s | %6d | %8.1f%% | %8.1f%% | %8.1f%% | %8.1f%%' % (
                cat, b_, n, 100.0 * (c['take'] + c['pass']) / n, 100.0 * c['take'] / n,
                100.0 * c['pass'] / n, 100.0 * c['missing'] / n))
        print('-' * 96)


main()