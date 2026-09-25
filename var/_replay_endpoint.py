# -*- coding: utf-8 -*-
"""Replay-based paired endpoint for live A/B campaigns (READ-ONLY).

Motivation: the ledger endpoint (net score per room) carries SD=192 净胜/房, so a
+50 净胜/房 effect needs ~150 rooms/arm.  Portal replays carry the round-level
winner and fan, so a per-room 和牌率 endpoint has variance driven by hand
development rather than the x2/x4/x8 multiplier lottery.

Seat order differs from file to file (b0..b9) -> resolve ME's seat per file and
key rounds by (file, round_no).  Never touches the campaign.
"""
from __future__ import annotations
import collections, glob, io, json, math, os, statistics, sys

# ★ R1538：从 `__file__` 推（原 `ROOT = r'D:\hangzhouMaj'`）——
#   在 clone 里那个路径不存在 ⇒ 回放目录扫不到
#   ⇒ `_gate2` **静默报“房数不足”**（而不是报错）。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = 'u_7a3fba48d70b'
REPLAYS = os.path.join(ROOT, 'var', 'replays')


def load_rows(path=None):
    path = path or os.path.join(ROOT, 'var', 'auto_ranking.jsonl')
    out = []
    for ln in io.open(path, encoding='utf-8'):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def room_index():
    idx = collections.defaultdict(list)
    for fold in ('recent', 'server'):
        for f in glob.glob(os.path.join(REPLAYS, fold, '*.json')):
            idx[os.path.basename(f).split('_r')[0]].append(f)
    return idx


def room_rounds(files, me_uid=ME):
    """(file, round_no) -> record, over blocks carrying full start_hands."""
    rounds = {}
    for f in files:
        try:
            d = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        seats = d.get('seats') or []
        if len(seats) != 4:
            continue
        uids = [(s.get('user_id') or '') for s in seats]
        if me_uid not in uids:
            continue
        mys = uids.index(me_uid)
        base = os.path.basename(f)
        for b in d.get('blocks') or []:
            rn = b.get('round_no')
            if rn is None:
                continue
            rec = rounds.setdefault((base, rn), {
                'my_win': False, 'my_fan': 0, 'draw': None, 'full': False,
                'melds': 0, 'an': 0, 'bu': 0, 'ming': 0, 'detail': None,
                'seen': set()})
            sh = b.get('start_hands')
            if sh and len(sh) == 4 and all(isinstance(x, (list, tuple)) for x in sh):
                rec['full'] = True
                rec['start'] = sh
                rec['dealer'] = b.get('dealer')
            for e in b.get('events') or []:
                t = e.get('type')
                sq = e.get('seq')
                if t == 'round_ended':
                    dd = e.get('data') or {}
                    wseat = e.get('seat')
                    rec['my_win'] = (wseat == mys)
                    rec['draw'] = bool(dd.get('draw'))
                    if wseat == mys:
                        rec['my_fan'] = int(dd.get('fan') or 0)
                        rec['detail'] = dd.get('detail')
                elif t in ('chi', 'peng', 'gang') and e.get('seat') == mys:
                    if sq not in rec['seen']:
                        rec['seen'].add(sq)
                        rec['melds'] += 1
                        if t == 'gang':
                            knd = (e.get('data') or {}).get('kind')
                            if knd in ('an', 'bu', 'ming'):
                                rec[knd] += 1
    return {k: v for k, v in rounds.items() if v['full']}


def collect(since):
    rows = load_rows()
    camp = collections.defaultdict(set)
    for r in rows:
        if (r.get('ts') or '') >= since:
            camp[r['room']].add(r.get('strategy'))
    idx = room_index()
    out = collections.defaultdict(list)
    missing = 0
    for room, strats in sorted(camp.items()):
        if len(strats) != 1:
            continue
        arm = next(iter(strats))
        files = idx.get(room)
        if not files:
            missing += 1
            continue
        rr = room_rounds(files)
        R = len(rr)
        if R < 60:
            missing += 1
            continue
        wins = sum(1 for v in rr.values() if v['my_win'])
        det = [x for v in rr.values() for x in (v.get('detail') or [])]
        out[arm].append({
            'room': room, 'R': R,
            'hu': 100.0 * wins / R,
            'fan': sum(v['my_fan'] for v in rr.values()) / R,
            'melds': sum(v['melds'] for v in rr.values()),
            'ming': sum(v['ming'] for v in rr.values()),
            'an': sum(v['an'] for v in rr.values()),
            'bu': sum(v['bu'] for v in rr.values()),
            'baotou': sum(1 for x in det if '爆头' in str(x)),
            'piao': sum(1 for x in det if '财飘' in str(x)),
            'gangkai': sum(1 for x in det if '杠开' in str(x)),
            'qidui': sum(1 for x in det if '七对' in str(x)),
        })
    return out, missing


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else '2026-09-20 14:54:07'
    dat, missing = collect(since)
    arms = sorted(dat)
    print('replay endpoint since=%s  usable rooms/arm=%s  (skipped %d)'
          % (since, {a: len(dat[a]) for a in arms}, missing))
    if not arms:
        return
    keys = ['hu', 'fan', 'melds', 'ming', 'an', 'bu', 'baotou', 'piao', 'gangkai', 'qidui']
    for a in arms:
        print('  %-12s ' % a + '  '.join(
            '%s=%.2f' % (k, statistics.mean([x[k] for x in dat[a]])) for k in keys)
            + '  n=%d' % len(dat[a]))
    if len(arms) == 2:
        a, b = arms
        for k in keys:
            va = [x[k] for x in dat[a]]
            vb = [x[k] for x in dat[b]]
            d = statistics.mean(vb) - statistics.mean(va)
            if len(va) < 2 or len(vb) < 2:
                continue
            se = math.sqrt(statistics.variance(va) / len(va) + statistics.variance(vb) / len(vb))
            if d == 0 or se == 0:
                print('  Δ%-9s (b-a) = %+8.3f   SE=%.3f  (no signal)' % (k, d, se))
                continue
            n_need = (1.5 ** 2) * (se ** 2) * (1.0 / len(va) + 1.0 / len(vb)) / (d ** 2)
            print('  Δ%-9s (b-a) = %+8.3f   SE=%.3f  z=%+.2f   [z=1.5 需 %.0f 房/臂]'
                  % (k, d, se, d / se, n_need))


if __name__ == '__main__':
    main()
