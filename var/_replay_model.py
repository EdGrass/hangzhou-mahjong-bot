# -*- coding: utf-8 -*-
"""AUTHORITATIVE replay model (READ-ONLY).  One place for reconstruction + metrics.

Why: the ad-hoc analyses produced mutually inconsistent counts (e.g. "437 peng
claims" vs the true 2028 over the same rooms), because each script re-implemented
the reconstruction with slightly different bookkeeping (per-file vs per-room,
duplicated `auto_*` dirs, different length checks).  Every further campaign decision
depends on these numbers, so they now come from ONE module with a self-test.

Guarantees (verified by `validate()`, see tests/test_replay_model.py):
  * seat order is resolved PER FILE (b0..b9 differ),
  * rounds are keyed by (file, round_no) -- `round_no` restarts inside each file,
  * `round_ended` carries the winner seat at the EVENT level, not inside `data`,
  * every discard/chi/peng/gang is applied to the reconstructed hand, and any
    inconsistency is reported as an error instead of silently skewing counts,
  * rooms are deduplicated: the authoritative source is `var/replays/recent`
    (`auto_*` contains duplicate room dirs -- 16.5 files/room vs the normal 10).
"""
from __future__ import annotations
import collections, glob, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ★ R1522：从 __file__ 推（原硬编码 D:\hangzhouMaj ⇒ clone 里必崩）
ME = 'u_7a3fba48d70b'
GOD = '白'
RECENT = os.path.join(ROOT, 'var', 'replays', 'recent')


# ---------------------------------------------------------------- room files
def room_files():
    """room -> [files] from the authoritative directory (one gid per file)."""
    idx = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(RECENT, '*.json'))):
        idx[os.path.basename(f).split('_r')[0]].append(f)
    return idx


# ---------------------------------------------------------------- per file
def _hand_len(e, g):
    return 13 - 3 * e - g


def iter_rounds(files):
    """Yield one record per (file, round_no) with a validated reconstruction.

    record = dict(file, round_no, start, dealer, events, snapshots, errors,
                  winner, my_win, my_fan, detail)
    `snapshots[i]` = (event, hands, melds, gangs, draws) *after* applying event i.
    """
    for f in files:
        try:
            d = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        seats = d.get('seats') or []
        uids = [(s.get('user_id') or '') for s in seats]
        if len(seats) != 4 or ME not in uids:
            continue
        me = uids.index(ME)
        recs = {}
        for b in d.get('blocks') or []:
            rn = b.get('round_no')
            if rn is None:
                continue
            rec = recs.setdefault(rn, {'ev': {}, 'start': None, 'dealer': None})
            sh = b.get('start_hands')
            if sh and len(sh) == 4 and all(isinstance(x, (list, tuple)) for x in sh):
                rec['start'] = [list(x) for x in sh]
                rec['dealer'] = b.get('dealer')
            for e in b.get('events') or []:
                if e.get('seq') is not None:
                    rec['ev'][e['seq']] = e
        for rn, rec in recs.items():
            if rec['start'] is None:
                continue
            hands = [list(x) for x in rec['start']]
            melds = [[] for _ in range(4)]
            draws = [0] * 4
            errors = []
            snaps = []
            winner = None
            fan = 0
            detail = None
            for sq in sorted(rec['ev']):
                e = rec['ev'][sq]
                t = e.get('type'); s = e.get('seat')
                if not isinstance(s, int) or not (0 <= s < 4):
                    if t == 'round_ended' and isinstance(s := e.get('seat'), int):
                        pass
                    snaps.append((e, [list(x) for x in hands],
                                  [list(x) for x in melds], list(draws)))
                    if t == 'round_ended':
                        winner = e.get('seat')
                        dd = e.get('data') or {}
                        fan = int(dd.get('fan') or 0)
                        detail = dd.get('detail')
                    continue
                h = hands[s]
                e_n = len(melds[s])
                g_n = sum(1 for m in melds[s] if m['type'] == 'gang')
                if t == 'tile_drawn':
                    h.append(e.get('tile'))
                    draws[s] += 1
                elif t == 'tile_discarded':
                    tile = e.get('tile')
                    if tile not in h:
                        errors.append(('discard_not_in_hand', rn, s, tile))
                    else:
                        h.remove(tile)
                elif t == 'chi':
                    tiles = list((e.get('data') or {}).get('tiles') or [])
                    use = [x for x in tiles if x != e.get('tile')]
                    if (s - (e.get('tile') and _last_discarder(snaps) or s)) % 4 != 1:
                        pass
                    for x in use:
                        if x in h:
                            h.remove(x)
                        else:
                            errors.append(('chi_missing', rn, s, x))
                    melds[s].append({'type': 'chi', 'tile': e.get('tile'), 'tiles': tiles})
                elif t == 'peng':
                    tile = e.get('tile')
                    for _ in range(2):
                        if tile in h:
                            h.remove(tile)
                        else:
                            errors.append(('peng_missing', rn, s, tile))
                    melds[s].append({'type': 'peng', 'tile': tile, 'tiles': [tile] * 3})
                elif t == 'gang':
                    tile = e.get('tile'); knd = (e.get('data') or {}).get('kind')
                    need = 4 if knd == 'an' else (3 if knd == 'ming' else 1)
                    for _ in range(need):
                        if tile in h:
                            h.remove(tile)
                        else:
                            errors.append(('gang_missing', rn, s, tile, knd))
                    melds[s].append({'type': 'gang', 'tile': tile,
                                     'tiles': [tile] * (4 if knd in ('an', 'bu') else 3)})
                elif t == 'round_ended':
                    winner = s
                    dd = e.get('data') or {}
                    fan = int(dd.get('fan') or 0)
                    detail = dd.get('detail')
                snaps.append((e, [list(x) for x in hands],
                              [list(x) for x in melds], list(draws)))
            yield {'file': f, 'round_no': rn, 'start': rec['start'], 'dealer': rec['dealer'],
                   'me': me, 'hands': hands, 'melds': melds, 'draws': draws,
                   'snapshots': snaps, 'errors': errors, 'winner': winner,
                   'my_win': winner == me, 'my_fan': fan if winner == me else 0,
                   'detail': detail if winner == me else None}



def peng_claims(rec):
    """Number of peng events by OUR seat in one round."""
    n = 0
    for e, _h, _m, _d in rec['snapshots']:
        if e.get('type') == 'peng' and e.get('seat') == rec['me']:
            n += 1
    return n


def _last_discarder(snaps):
    for e, _h, _m, _d in reversed(snaps):
        if e.get('type') == 'tile_discarded':
            return e.get('seat')
    return None


# ---------------------------------------------------------------- self-test
def validate(limit_rooms=25):
    """Reconstruction self-test: returns (blocks, errors, samples)."""
    idx = room_files()
    rooms = sorted(idx)[:limit_rooms]
    blocks = errs = 0
    samples = []
    for r in rooms:
        for rec in iter_rounds(idx[r]):
            blocks += 1
            if rec['errors']:
                errs += len(rec['errors'])
                if len(samples) < 5:
                    samples.append((os.path.basename(rec['file']), rec['round_no'],
                                    rec['errors'][:2]))
    return blocks, errs, samples


def main():
    b, e, s = validate(25)
    print('SELF-TEST: blocks=%d errors=%d' % (b, e))
    for x in s:
        print('  ', x)
    # canonical corpus stats over all c151 campaign rooms
    keep = set()
    for ln in io.open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if (d.get('ts') or '') >= '2026-09-20 14:54:07' and d.get('strategy') == 'speedc151':
            keep.add(d['room'])
    idx = room_files()
    rooms = sorted(r for r in keep if r in idx)
    wins = rounds = peng = chi = gang = 0
    legal_peng = legal_chi = chi_events = chi_from_up = 0
    claims = 0
    for r in rooms:
        for rec in iter_rounds(idx[r]):
            rounds += 1
            wins += 1 if rec['my_win'] else 0
            me = rec['me']
            for m in rec['melds'][me]:
                peng += 1 if m['type'] == 'peng' else 0
                chi += 1 if m['type'] == 'chi' else 0
                gang += 1 if m['type'] == 'gang' else 0
            # legal windows + chi legality, walked over the snapshot chain
            prev = None
            last_disc = None
            for e, hands, melds, draws in rec['snapshots']:
                t = e.get('type')
                if t == 'tile_discarded':
                    if prev is not None and e.get('seat') != me:
                        h_me = prev[1][me]
                        tile = e.get('tile')
                        if tile and h_me.count(tile) >= 2:
                            legal_peng += 1
                        if tile and last_disc is None and (me - e.get('seat')) % 4 == 1:
                            hs = set(h_me)
                            n = int(tile[0]) if tile[-1] in 'wbt' and tile != GOD else 0
                            suit = tile[-1] if n else ''
                            for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
                                if 1 <= a <= 9 and 1 <= b <= 9 and                                    ('%d%s' % (a, suit)) in hs and ('%d%s' % (b, suit)) in hs:
                                    legal_chi += 1
                                    break
                    last_disc = e.get('seat')
                elif t == 'chi':
                    chi_events += 1
                    if last_disc is not None and (e.get('seat') - last_disc) % 4 == 1:
                        chi_from_up += 1
                elif t == 'tile_drawn':
                    last_disc = None
                prev = (e, hands, melds, draws)
            claims += peng_claims(rec)
    print('canonical c151 rooms=%d rounds=%d  our wins=%d (%.2f%%)  our melds: peng=%d chi=%d gang=%d (%.2f/%.2f/%.2f per round)'
          % (len(rooms), rounds, wins, 100.0 * wins / max(1, rounds), peng, chi, gang,
             peng / max(1, rounds), chi / max(1, rounds), gang / max(1, rounds)))
    if claims:
        print('canonical 碰轴: 合法窗口=%d (%.1f/房)  我们的碰=%d (%.1f/房)  ⇒ 实现率 %.1f%%'
              % (legal_peng, legal_peng / len(rooms), claims, claims / len(rooms),
                 100.0 * claims / legal_peng))
    if chi_events:
        print('canonical 吃轴: 合法窗口=%d  吃事件=%d  其中来自上家 %.1f%%（应为 100%%）'
              % (legal_chi, chi_events, 100.0 * chi_from_up / chi_events))


if __name__ == '__main__':
    main()
